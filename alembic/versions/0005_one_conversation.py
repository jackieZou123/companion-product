"""one conversation per user and character

Revision ID: 0005_one_conversation
Revises: 0004_nudges
Create Date: 2026-09-17
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql import bindparam

revision: str = "0005_one_conversation"
down_revision: Union[str, Sequence[str], None] = "0004_nudges"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 先丢掉旧的重复会话，再锁唯一约束
    conn = op.get_bind()
    rows = conn.execute(
        sa.text(
            "SELECT id, user_id, character_id, updated_at FROM conversations"
        )
    ).fetchall()
    keep: dict[tuple[str, str], str] = {}
    drop: list[str] = []
    for row in sorted(rows, key=lambda item: item.updated_at, reverse=True):
        key = (row.user_id, row.character_id)
        if key in keep:
            drop.append(row.id)
        else:
            keep[key] = row.id
    if drop:
        delete_messages = sa.text(
            "DELETE FROM messages WHERE conversation_id IN :ids"
        ).bindparams(bindparam("ids", expanding=True))
        delete_conversations = sa.text(
            "DELETE FROM conversations WHERE id IN :ids"
        ).bindparams(bindparam("ids", expanding=True))
        conn.execute(delete_messages, {"ids": drop})
        conn.execute(delete_conversations, {"ids": drop})
    with op.batch_alter_table("conversations") as batch:
        batch.create_unique_constraint(
            "uq_conversation_user_character", ["user_id", "character_id"]
        )


def downgrade() -> None:
    with op.batch_alter_table("conversations") as batch:
        batch.drop_constraint("uq_conversation_user_character", type_="unique")
