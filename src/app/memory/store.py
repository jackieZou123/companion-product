"""长期记忆持久化。按 user_id + character_id 隔离。"""

from datetime import datetime, timezone

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.models import MemoryEventRow, MemoryProfileRow, MemoryRelationshipRow
from app.memory.errors import InvalidMemoryProfileError, MemoryEventNotFoundError
from app.memory.extract import ALLOWED_VALUES, PROFILE_SLOTS, extract
from app.memory.models import (
    MemoryEvent,
    MemorySnapshot,
    ProfileSlot,
    relationship_stage,
)

EVENT_LIMIT = 50


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class SqlMemoryStore:
    """画像覆盖、事件追加、关系计数。纠正走同一套表。"""

    def __init__(self, session_factory: async_sessionmaker) -> None:
        self._session_factory = session_factory

    async def recall(self, user_id: str, character_id: str) -> MemorySnapshot:
        async with self._session_factory() as session:
            profile_rows = (
                (
                    await session.execute(
                        select(MemoryProfileRow)
                        .where(
                            MemoryProfileRow.user_id == user_id,
                            MemoryProfileRow.character_id == character_id,
                        )
                        .order_by(MemoryProfileRow.slot.asc())
                    )
                )
                .scalars()
                .all()
            )
            event_rows = (
                (
                    await session.execute(
                        select(MemoryEventRow)
                        .where(
                            MemoryEventRow.user_id == user_id,
                            MemoryEventRow.character_id == character_id,
                        )
                        .order_by(MemoryEventRow.id.desc())
                        .limit(EVENT_LIMIT)
                    )
                )
                .scalars()
                .all()
            )
            relation = (
                await session.execute(
                    select(MemoryRelationshipRow).where(
                        MemoryRelationshipRow.user_id == user_id,
                        MemoryRelationshipRow.character_id == character_id,
                    )
                )
            ).scalar_one_or_none()
        events = [
            MemoryEvent(
                id=row.id,
                slot=row.slot,
                value=row.value,
                source_text=row.source_text,
                source=row.source,
                created_at=row.created_at,
            )
            for row in reversed(list(event_rows))
        ]
        return MemorySnapshot(
            user_id=user_id,
            character_id=character_id,
            stage=relation.stage if relation is not None else "new",
            turn_count=relation.turn_count if relation is not None else 0,
            conversation_count=(
                relation.conversation_count if relation is not None else 0
            ),
            profile=[ProfileSlot(slot=row.slot, value=row.value) for row in profile_rows],
            events=events,
        )

    async def remember(
        self,
        user_id: str,
        character_id: str,
        user_text: str,
        conversation_id: str,
    ) -> MemorySnapshot:
        facts = extract(user_text)
        now = _utcnow()
        async with self._session_factory() as session:
            async with session.begin():
                relation = await self._touch_relationship(
                    session,
                    user_id,
                    character_id,
                    conversation_id,
                    now,
                )
                for fact in facts:
                    await self._upsert_profile(
                        session,
                        user_id=user_id,
                        character_id=character_id,
                        slot=fact.slot,
                        value=fact.value,
                        source="user_said",
                        conversation_id=conversation_id,
                        now=now,
                    )
                    session.add(
                        MemoryEventRow(
                            user_id=user_id,
                            character_id=character_id,
                            slot=fact.slot,
                            value=fact.value,
                            source_text=user_text,
                            source="user_said",
                            conversation_id=conversation_id,
                            created_at=now,
                        )
                    )
                profile_count = await self._profile_count(
                    session, user_id, character_id
                )
                relation.stage = relationship_stage(
                    profile_count=profile_count,
                    conversation_count=relation.conversation_count,
                    turn_count=relation.turn_count,
                )
                relation.updated_at = now
        return await self.recall(user_id, character_id)

    async def patch_profile(
        self,
        user_id: str,
        character_id: str,
        slot: str,
        value: str,
    ) -> MemorySnapshot:
        if slot not in PROFILE_SLOTS:
            raise InvalidMemoryProfileError(f"未知槽位 {slot}")
        cleaned = value.strip()
        now = _utcnow()
        async with self._session_factory() as session:
            async with session.begin():
                if not cleaned:
                    await session.execute(
                        delete(MemoryProfileRow).where(
                            MemoryProfileRow.user_id == user_id,
                            MemoryProfileRow.character_id == character_id,
                            MemoryProfileRow.slot == slot,
                        )
                    )
                else:
                    allowed = ALLOWED_VALUES[slot]
                    if cleaned not in allowed:
                        raise InvalidMemoryProfileError(f"槽位 {slot} 不接受 {cleaned}")
                    await self._upsert_profile(
                        session,
                        user_id=user_id,
                        character_id=character_id,
                        slot=slot,
                        value=cleaned,
                        source="user_corrected",
                        conversation_id=None,
                        now=now,
                    )
                    session.add(
                        MemoryEventRow(
                            user_id=user_id,
                            character_id=character_id,
                            slot=slot,
                            value=cleaned,
                            source_text="",
                            source="user_corrected",
                            conversation_id=None,
                            created_at=now,
                        )
                    )
                relation = (
                    await session.execute(
                        select(MemoryRelationshipRow).where(
                            MemoryRelationshipRow.user_id == user_id,
                            MemoryRelationshipRow.character_id == character_id,
                        )
                    )
                ).scalar_one_or_none()
                if relation is not None:
                    profile_count = await self._profile_count(
                        session, user_id, character_id
                    )
                    relation.stage = relationship_stage(
                        profile_count=profile_count,
                        conversation_count=relation.conversation_count,
                        turn_count=relation.turn_count,
                    )
                    relation.updated_at = now
        return await self.recall(user_id, character_id)

    async def delete_event(
        self, event_id: int, *, user_id: str, character_id: str
    ) -> None:
        async with self._session_factory() as session:
            async with session.begin():
                row = (
                    await session.execute(
                        select(MemoryEventRow).where(
                            MemoryEventRow.id == event_id,
                            MemoryEventRow.user_id == user_id,
                            MemoryEventRow.character_id == character_id,
                        )
                    )
                ).scalar_one_or_none()
                if row is None:
                    raise MemoryEventNotFoundError(event_id)
                await session.delete(row)

    async def delete_all(self, user_id: str, character_id: str) -> None:
        async with self._session_factory() as session:
            async with session.begin():
                await session.execute(
                    delete(MemoryEventRow).where(
                        MemoryEventRow.user_id == user_id,
                        MemoryEventRow.character_id == character_id,
                    )
                )
                await session.execute(
                    delete(MemoryProfileRow).where(
                        MemoryProfileRow.user_id == user_id,
                        MemoryProfileRow.character_id == character_id,
                    )
                )
                await session.execute(
                    delete(MemoryRelationshipRow).where(
                        MemoryRelationshipRow.user_id == user_id,
                        MemoryRelationshipRow.character_id == character_id,
                    )
                )

    async def delete_all_for_user(self, user_id: str) -> None:
        async with self._session_factory() as session:
            async with session.begin():
                await session.execute(
                    delete(MemoryEventRow).where(MemoryEventRow.user_id == user_id)
                )
                await session.execute(
                    delete(MemoryProfileRow).where(MemoryProfileRow.user_id == user_id)
                )
                await session.execute(
                    delete(MemoryRelationshipRow).where(
                        MemoryRelationshipRow.user_id == user_id
                    )
                )

    async def list_for_user(self, user_id: str) -> list[MemorySnapshot]:
        async with self._session_factory() as session:
            pairs = (
                await session.execute(
                    select(
                        MemoryRelationshipRow.user_id,
                        MemoryRelationshipRow.character_id,
                    ).where(MemoryRelationshipRow.user_id == user_id)
                )
            ).all()
            profile_pairs = (
                await session.execute(
                    select(
                        MemoryProfileRow.character_id,
                    )
                    .where(MemoryProfileRow.user_id == user_id)
                    .distinct()
                )
            ).all()
        character_ids = {row[1] for row in pairs} | {row[0] for row in profile_pairs}
        snapshots = [
            await self.recall(user_id, character_id)
            for character_id in sorted(character_ids)
        ]
        return snapshots

    async def _touch_relationship(
        self,
        session: AsyncSession,
        user_id: str,
        character_id: str,
        conversation_id: str,
        now: datetime,
    ) -> MemoryRelationshipRow:
        relation = (
            await session.execute(
                select(MemoryRelationshipRow).where(
                    MemoryRelationshipRow.user_id == user_id,
                    MemoryRelationshipRow.character_id == character_id,
                )
            )
        ).scalar_one_or_none()
        if relation is None:
            relation = MemoryRelationshipRow(
                user_id=user_id,
                character_id=character_id,
                stage="new",
                turn_count=1,
                conversation_count=1,
                last_conversation_id=conversation_id,
                updated_at=now,
            )
            session.add(relation)
            await session.flush()
            return relation
        relation.turn_count += 1
        if relation.last_conversation_id != conversation_id:
            relation.conversation_count += 1
            relation.last_conversation_id = conversation_id
        relation.updated_at = now
        return relation

    async def _upsert_profile(
        self,
        session: AsyncSession,
        *,
        user_id: str,
        character_id: str,
        slot: str,
        value: str,
        source: str,
        conversation_id: str | None,
        now: datetime,
    ) -> None:
        row = (
            await session.execute(
                select(MemoryProfileRow).where(
                    MemoryProfileRow.user_id == user_id,
                    MemoryProfileRow.character_id == character_id,
                    MemoryProfileRow.slot == slot,
                )
            )
        ).scalar_one_or_none()
        if row is None:
            session.add(
                MemoryProfileRow(
                    user_id=user_id,
                    character_id=character_id,
                    slot=slot,
                    value=value,
                    source=source,
                    conversation_id=conversation_id,
                    updated_at=now,
                )
            )
            return
        row.value = value
        row.source = source
        row.conversation_id = conversation_id
        row.updated_at = now

    async def _profile_count(
        self, session: AsyncSession, user_id: str, character_id: str
    ) -> int:
        rows = (
            (
                await session.execute(
                    select(MemoryProfileRow.id).where(
                        MemoryProfileRow.user_id == user_id,
                        MemoryProfileRow.character_id == character_id,
                    )
                )
            )
            .scalars()
            .all()
        )
        return len(list(rows))
