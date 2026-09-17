"""会话持久化。消息全量写入，不在这里做窗口截断。"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import delete, func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlalchemy.orm import selectinload

from app.character.address import address_for
from app.db.models import ConversationRow, MessageRow
from app.dialogue.errors import (
    AdultNotConfirmedError,
    ConversationNotFoundError,
    GenderRequiredError,
)
from app.dialogue.state import HistoryMessage


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class Conversation:
    id: str
    user_id: str
    character_id: str
    created_at: datetime
    updated_at: datetime
    adult_confirmed: bool = True
    gender: str = "female"
    messages: list[HistoryMessage] = field(default_factory=list)
    message_count: int = 0


# 数据库会话存储器
class SqlConversationStore:
    """Postgres / SQLite 都走这套。"""

    def __init__(self, session_factory: async_sessionmaker) -> None:
        self._session_factory = session_factory

    async def ping(self) -> None:
        async with self._session_factory() as session:
            await session.execute(text("SELECT 1"))

    async def create(
        self,
        user_id: str,
        character_id: str,
        *,
        adult_confirmed: bool,
        gender: str,
    ) -> Conversation:
        # 同一用户对同一角色只留一路，悬浮窗不能开出多段历史
        if not adult_confirmed:
            raise AdultNotConfirmedError()
        try:
            address_for(gender)
        except ValueError as exc:
            raise GenderRequiredError() from exc
        existing = await self._get_for_user_character(user_id, character_id)
        if existing is not None:
            return existing
        now = _utcnow()
        row = ConversationRow(
            id=str(uuid4()),
            user_id=user_id,
            character_id=character_id,
            adult_confirmed=True,
            gender=gender,
            created_at=now,
            updated_at=now,
        )
        try:
            async with self._session_factory() as session:
                async with session.begin():
                    session.add(row)
        except IntegrityError:
            raced = await self._get_for_user_character(user_id, character_id)
            if raced is None:
                raise
            return raced
        return _to_conversation(row, [])

    async def get(
        self, conversation_id: str, *, user_id: str | None = None
    ) -> Conversation:
        async with self._session_factory() as session:
            stmt = (
                select(ConversationRow)
                .options(selectinload(ConversationRow.messages))
                .where(ConversationRow.id == conversation_id)
            )
            if user_id is not None:
                stmt = stmt.where(ConversationRow.user_id == user_id)
            row = (await session.execute(stmt)).scalar_one_or_none()
        if row is None:
            raise ConversationNotFoundError(conversation_id)
        return _to_conversation(row, row.messages)

    async def list_for_user(self, user_id: str) -> list[Conversation]:
        async with self._session_factory() as session:
            rows = (
                (
                    await session.execute(
                        select(ConversationRow)
                        .where(ConversationRow.user_id == user_id)
                        .order_by(ConversationRow.updated_at.desc())
                    )
                )
                .scalars()
                .all()
            )
            if not rows:
                return []
            counts = dict(
                (
                    await session.execute(
                        select(MessageRow.conversation_id, func.count(MessageRow.id))
                        .where(MessageRow.conversation_id.in_([row.id for row in rows]))
                        .group_by(MessageRow.conversation_id)
                    )
                ).all()
            )
        return [
            _to_conversation(row, [], message_count=int(counts.get(row.id, 0)))
            for row in rows
        ]

    async def latest_for_user(self, user_id: str, character_id: str) -> Conversation | None:
        return await self._get_for_user_character(user_id, character_id)

    async def _get_for_user_character(
        self, user_id: str, character_id: str
    ) -> Conversation | None:
        async with self._session_factory() as session:
            row = (
                await session.execute(
                    select(ConversationRow)
                    .options(selectinload(ConversationRow.messages))
                    .where(
                        ConversationRow.user_id == user_id,
                        ConversationRow.character_id == character_id,
                    )
                    .order_by(ConversationRow.updated_at.desc())
                    .limit(1)
                )
            ).scalar_one_or_none()
        if row is None:
            return None
        return _to_conversation(row, row.messages)

    async def export_for_user(self, user_id: str) -> list[Conversation]:
        async with self._session_factory() as session:
            rows = (
                (
                    await session.execute(
                        select(ConversationRow)
                        .options(selectinload(ConversationRow.messages))
                        .where(ConversationRow.user_id == user_id)
                        .order_by(ConversationRow.created_at.asc())
                    )
                )
                .scalars()
                .all()
            )
        return [_to_conversation(row, row.messages) for row in rows]

    async def delete(self, conversation_id: str, *, user_id: str) -> None:
        async with self._session_factory() as session:
            async with session.begin():
                row = (
                    await session.execute(
                        select(ConversationRow).where(
                            ConversationRow.id == conversation_id,
                            ConversationRow.user_id == user_id,
                        )
                    )
                ).scalar_one_or_none()
                if row is None:
                    raise ConversationNotFoundError(conversation_id)
                await session.execute(
                    delete(MessageRow).where(
                        MessageRow.conversation_id == conversation_id
                    )
                )
                await session.delete(row)

    async def delete_all_for_user(self, user_id: str) -> int:
        async with self._session_factory() as session:
            async with session.begin():
                ids = list(
                    (
                        await session.execute(
                            select(ConversationRow.id).where(
                                ConversationRow.user_id == user_id
                            )
                        )
                    )
                    .scalars()
                    .all()
                )
                if not ids:
                    return 0
                await session.execute(
                    delete(MessageRow).where(MessageRow.conversation_id.in_(ids))
                )
                await session.execute(
                    delete(ConversationRow).where(ConversationRow.id.in_(ids))
                )
                return len(ids)

    async def append(
        self, conversation_id: str, user_text: str, assistant_text: str
    ) -> None:
        # 行锁 + 唯一约束重试，避免并发 turn 撞 seq
        last_error: Exception | None = None
        for _ in range(4):
            try:
                await self._append_once(conversation_id, user_text, assistant_text)
                return
            except IntegrityError as exc:
                last_error = exc
        if last_error is not None:
            raise last_error

    async def _append_once(
        self, conversation_id: str, user_text: str, assistant_text: str
    ) -> None:
        async with self._session_factory() as session:
            async with session.begin():
                conversation = (
                    await session.execute(
                        select(ConversationRow)
                        .where(ConversationRow.id == conversation_id)
                        .with_for_update()
                    )
                ).scalar_one_or_none()
                if conversation is None:
                    raise ConversationNotFoundError(conversation_id)
                next_seq = (
                    await session.scalar(
                        select(func.coalesce(func.max(MessageRow.seq), 0)).where(
                            MessageRow.conversation_id == conversation_id
                        )
                    )
                    or 0
                )
                now = _utcnow()
                session.add(
                    MessageRow(
                        conversation_id=conversation_id,
                        seq=next_seq + 1,
                        role="user",
                        content=user_text,
                        created_at=now,
                    )
                )
                session.add(
                    MessageRow(
                        conversation_id=conversation_id,
                        seq=next_seq + 2,
                        role="assistant",
                        content=assistant_text,
                        created_at=now,
                    )
                )
                conversation.updated_at = now


# 转换为对话对象
def _to_conversation(
    row: ConversationRow,
    messages: list[MessageRow],
    *,
    message_count: int | None = None,
) -> Conversation:
    packed = [{"role": item.role, "content": item.content} for item in messages]
    return Conversation(
        id=row.id,
        user_id=row.user_id,
        character_id=row.character_id,
        created_at=row.created_at,
        updated_at=row.updated_at,
        adult_confirmed=bool(row.adult_confirmed),
        gender=row.gender or "female",
        messages=[
            HistoryMessage(role=item["role"], content=item["content"])
            for item in packed
        ],
        message_count=len(packed) if message_count is None else message_count,
    )
