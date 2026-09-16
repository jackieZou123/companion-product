"""会话、消息和长期记忆表。"""

from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class ConversationRow(Base):
    __tablename__ = "conversations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(64), index=True)
    character_id: Mapped[str] = mapped_column(String(64), index=True)
    adult_confirmed: Mapped[bool] = mapped_column(Boolean, default=True)
    # female / male，用来称姐姐或哥哥
    gender: Mapped[str] = mapped_column(String(16), default="female")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    messages: Mapped[list["MessageRow"]] = relationship(
        back_populates="conversation",
        cascade="all, delete-orphan",
        order_by="MessageRow.seq",
    )


class MessageRow(Base):
    __tablename__ = "messages"
    __table_args__ = (UniqueConstraint("conversation_id", "seq", name="uq_message_seq"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    conversation_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("conversations.id", ondelete="CASCADE"), index=True
    )
    seq: Mapped[int] = mapped_column(Integer)
    role: Mapped[str] = mapped_column(String(16))
    content: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    conversation: Mapped[ConversationRow] = relationship(back_populates="messages")


class MemoryProfileRow(Base):
    """当前画像槽位。同一用户+角色+槽位只保留最新值。"""

    __tablename__ = "memory_profile"
    __table_args__ = (
        UniqueConstraint("user_id", "character_id", "slot", name="uq_memory_profile_slot"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(64), index=True)
    character_id: Mapped[str] = mapped_column(String(64), index=True)
    slot: Mapped[str] = mapped_column(String(32))
    value: Mapped[str] = mapped_column(String(64))
    source: Mapped[str] = mapped_column(String(32), default="user_said")
    conversation_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class MemoryEventRow(Base):
    """画像变更来源。可按条删除，不自动回滚槽位。"""

    __tablename__ = "memory_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(64), index=True)
    character_id: Mapped[str] = mapped_column(String(64), index=True)
    slot: Mapped[str] = mapped_column(String(32))
    value: Mapped[str] = mapped_column(String(64))
    source_text: Mapped[str] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String(32), default="user_said")
    conversation_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class MemoryRelationshipRow(Base):
    """一对用户+角色的关系阶段。"""

    __tablename__ = "memory_relationship"

    user_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    character_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    stage: Mapped[str] = mapped_column(String(16), default="new")
    turn_count: Mapped[int] = mapped_column(Integer, default=0)
    conversation_count: Mapped[int] = mapped_column(Integer, default=0)
    last_conversation_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
