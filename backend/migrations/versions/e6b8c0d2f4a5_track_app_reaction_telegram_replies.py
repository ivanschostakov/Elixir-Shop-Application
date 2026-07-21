"""track app reaction telegram replies

Revision ID: e6b8c0d2f4a5
Revises: d5a7b9c1e3f4
Create Date: 2026-07-22 01:30:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "e6b8c0d2f4a5"
down_revision = "d5a7b9c1e3f4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "community_reactions",
        sa.Column("telegram_chat_id", sa.BigInteger(), nullable=True),
    )
    op.add_column(
        "community_reactions",
        sa.Column("telegram_message_id", sa.BigInteger(), nullable=True),
    )
    op.create_index(
        "ix_community_reactions_telegram_message_id",
        "community_reactions",
        ["telegram_message_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_community_reactions_telegram_message_id",
        table_name="community_reactions",
    )
    op.drop_column("community_reactions", "telegram_message_id")
    op.drop_column("community_reactions", "telegram_chat_id")
