"""主动消息持久化。按 user_id + character_id 隔离。"""

from datetime import datetime, timezone

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db.models import NudgeRow
from app.nudge.errors import NudgeNotFoundError
from app.nudge.models import Nudge


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class SqlNudgeStore:
    """待取、ack、忽略。过期记录仍留着给频控看 created_at。"""

    def __init__(self, session_factory: async_sessionmaker) -> None:
        self._session_factory = session_factory

    async def list_pending(
        self, user_id: str, character_id: str, *, now: datetime
    ) -> list[Nudge]:
        async with self._session_factory() as session:
            rows = (
                (
                    await session.execute(
                        select(NudgeRow)
                        .where(
                            NudgeRow.user_id == user_id,
                            NudgeRow.character_id == character_id,
                            NudgeRow.acked_at.is_(None),
                            NudgeRow.dismissed_at.is_(None),
                            NudgeRow.expires_at > now,
                        )
                        .order_by(NudgeRow.id.asc())
                    )
                )
                .scalars()
                .all()
            )
        return [_to_nudge(row) for row in rows]

    async def list_for_user(self, user_id: str, *, now: datetime) -> list[Nudge]:
        async with self._session_factory() as session:
            rows = (
                (
                    await session.execute(
                        select(NudgeRow)
                        .where(
                            NudgeRow.user_id == user_id,
                            NudgeRow.acked_at.is_(None),
                            NudgeRow.dismissed_at.is_(None),
                            NudgeRow.expires_at > now,
                        )
                        .order_by(NudgeRow.id.asc())
                    )
                )
                .scalars()
                .all()
            )
        return [_to_nudge(row) for row in rows]

    async def last_created_at(self, user_id: str, character_id: str) -> datetime | None:
        async with self._session_factory() as session:
            value = await session.scalar(
                select(func.max(NudgeRow.created_at)).where(
                    NudgeRow.user_id == user_id,
                    NudgeRow.character_id == character_id,
                )
            )
        return value

    async def create(
        self,
        *,
        user_id: str,
        character_id: str,
        code: str,
        text: str,
        created_at: datetime,
        expires_at: datetime,
    ) -> Nudge:
        row = NudgeRow(
            user_id=user_id,
            character_id=character_id,
            code=code,
            text=text,
            created_at=created_at,
            expires_at=expires_at,
        )
        async with self._session_factory() as session:
            async with session.begin():
                session.add(row)
                await session.flush()
                return _to_nudge(row)

    async def ack(self, nudge_id: int, *, user_id: str, now: datetime | None = None) -> Nudge:
        return await self._mark(nudge_id, user_id=user_id, field="acked_at", now=now)

    async def dismiss(self, nudge_id: int, *, user_id: str, now: datetime | None = None) -> Nudge:
        return await self._mark(nudge_id, user_id=user_id, field="dismissed_at", now=now)

    async def delete_all_for_user(self, user_id: str) -> None:
        async with self._session_factory() as session:
            async with session.begin():
                await session.execute(delete(NudgeRow).where(NudgeRow.user_id == user_id))

    async def _mark(
        self,
        nudge_id: int,
        *,
        user_id: str,
        field: str,
        now: datetime | None,
    ) -> Nudge:
        stamped = now or _utcnow()
        async with self._session_factory() as session:
            async with session.begin():
                row = (
                    await session.execute(
                        select(NudgeRow).where(
                            NudgeRow.id == nudge_id,
                            NudgeRow.user_id == user_id,
                        )
                    )
                ).scalar_one_or_none()
                if row is None:
                    raise NudgeNotFoundError(nudge_id)
                if field == "acked_at" and row.acked_at is None:
                    row.acked_at = stamped
                if field == "dismissed_at" and row.dismissed_at is None:
                    row.dismissed_at = stamped
                await session.flush()
                return _to_nudge(row)


def _to_nudge(row: NudgeRow) -> Nudge:
    return Nudge(
        id=row.id,
        user_id=row.user_id,
        character_id=row.character_id,
        code=row.code,
        text=row.text,
        created_at=row.created_at,
        expires_at=row.expires_at,
        acked_at=row.acked_at,
        dismissed_at=row.dismissed_at,
    )
