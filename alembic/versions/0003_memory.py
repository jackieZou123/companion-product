"""long-term memory tables

Revision ID: 0003_memory
Revises: 0002_gender
Create Date: 2026-09-16
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0003_memory"
down_revision: Union[str, Sequence[str], None] = "0002_gender"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "memory_profile",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.String(length=64), nullable=False, index=True),
        sa.Column("character_id", sa.String(length=64), nullable=False, index=True),
        sa.Column("slot", sa.String(length=32), nullable=False),
        sa.Column("value", sa.String(length=64), nullable=False),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("conversation_id", sa.String(length=36), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("user_id", "character_id", "slot", name="uq_memory_profile_slot"),
    )
    op.create_table(
        "memory_events",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.String(length=64), nullable=False, index=True),
        sa.Column("character_id", sa.String(length=64), nullable=False, index=True),
        sa.Column("slot", sa.String(length=32), nullable=False),
        sa.Column("value", sa.String(length=64), nullable=False),
        sa.Column("source_text", sa.Text(), nullable=False),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("conversation_id", sa.String(length=36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "memory_relationship",
        sa.Column("user_id", sa.String(length=64), primary_key=True),
        sa.Column("character_id", sa.String(length=64), primary_key=True),
        sa.Column("stage", sa.String(length=16), nullable=False),
        sa.Column("turn_count", sa.Integer(), nullable=False),
        sa.Column("conversation_count", sa.Integer(), nullable=False),
        sa.Column("last_conversation_id", sa.String(length=36), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("memory_relationship")
    op.drop_table("memory_events")
    op.drop_table("memory_profile")
