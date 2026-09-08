"""add conversation gender

Revision ID: 0002_gender
Revises: 0001_initial
Create Date: 2026-09-08
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0002_gender"
down_revision: Union[str, Sequence[str], None] = "0001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 已有行给占位，新会话仍由接口强制传入
    op.add_column(
        "conversations",
        sa.Column(
            "gender",
            sa.String(length=16),
            nullable=False,
            server_default="female",
        ),
    )


def downgrade() -> None:
    op.drop_column("conversations", "gender")
