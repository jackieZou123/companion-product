"""会话持久化。消息全量写入，不在这里做窗口截断。"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlalchemy.orm import selectinload

from app.db.models import ConversationRow, MessageRow
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
    messages: list[HistoryMessage] = field(default_factory=list)


class ConversationNotFoundError(KeyError):
    pass


# 数据库会话存储器
class SqlConversationStore:
    """Postgres / SQLite 都走这套。"""

    def __init__(self, session_factory: async_sessionmaker) -> None:
        self._session_factory = session_factory

    async def ping(self) -> None:
        async with self._session_factory() as session:
            await session.execute(text("SELECT 1"))

    async def create(self, user_id: str, character_id: str) -> Conversation:
        now = _utcnow()
        row = ConversationRow(
            id=str(uuid4()),
            user_id=user_id,
            character_id=character_id,
            created_at=now,
            updated_at=now,
        )
        async with self._session_factory() as session:
            async with session.begin():
                session.add(row)
        return _to_conversation(row, [])

    async def get(self, conversation_id: str) -> Conversation:
        async with self._session_factory() as session:
            result = await session.execute(
                select(ConversationRow)
                .options(selectinload(ConversationRow.messages))
                .where(ConversationRow.id == conversation_id)
            )
            row = result.scalar_one_or_none()
        if row is None:
            raise ConversationNotFoundError(conversation_id)
        return _to_conversation(row, row.messages)

    async def append(
        self, conversation_id: str, user_text: str, assistant_text: str
    ) -> None:
        async with self._session_factory() as session:
            async with session.begin():
                conversation = await session.get(ConversationRow, conversation_id)
                if conversation is None:
                    raise ConversationNotFoundError(conversation_id)
                next_seq = await session.scalar(
                    select(func.coalesce(func.max(MessageRow.seq), 0)).where(
                        MessageRow.conversation_id == conversation_id
                    )
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
def _to_conversation(row: ConversationRow, messages: list[MessageRow]) -> Conversation:
    return Conversation(
        id=row.id,
        user_id=row.user_id,
        character_id=row.character_id,
        created_at=row.created_at,
        updated_at=row.updated_at,
        messages=[{"role": item.role, "content": item.content} for item in messages],
    )
