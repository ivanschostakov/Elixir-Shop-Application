"""add user push tokens

Revision ID: d5e8f1a3c9b2
Revises: c61b7b1f96f3
Create Date: 2026-04-23 19:45:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "d5e8f1a3c9b2"
down_revision: Union[str, Sequence[str], None] = "c61b7b1f96f3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "user_push_tokens",
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("expo_push_token", sa.String(length=128), nullable=False),
        sa.Column("platform", sa.String(length=32), nullable=True),
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("expo_push_token"),
    )
    op.create_index(op.f("ix_user_push_tokens_id"), "user_push_tokens", ["id"], unique=False)
    op.create_index(op.f("ix_user_push_tokens_user_id"), "user_push_tokens", ["user_id"], unique=False)
    op.create_index(op.f("ix_user_push_tokens_expo_push_token"), "user_push_tokens", ["expo_push_token"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_user_push_tokens_expo_push_token"), table_name="user_push_tokens")
    op.drop_index(op.f("ix_user_push_tokens_user_id"), table_name="user_push_tokens")
    op.drop_index(op.f("ix_user_push_tokens_id"), table_name="user_push_tokens")
    op.drop_table("user_push_tokens")
