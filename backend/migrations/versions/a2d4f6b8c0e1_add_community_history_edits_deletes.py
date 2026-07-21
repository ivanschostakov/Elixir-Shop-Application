"""add community history edit and delete synchronization

Revision ID: a2d4f6b8c0e1
Revises: f7c2a9d4e1b6
Create Date: 2026-07-21 02:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "a2d4f6b8c0e1"
down_revision = "f7c2a9d4e1b6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("community_messages", sa.Column("edited_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("community_messages", sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_community_messages_edited_at", "community_messages", ["edited_at"])
    op.create_index("ix_community_messages_deleted_at", "community_messages", ["deleted_at"])

    op.add_column("community_telegram_parts", sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_community_telegram_parts_deleted_at", "community_telegram_parts", ["deleted_at"])

    op.add_column("community_topics", sa.Column("telegram_history_min_message_id", sa.BigInteger(), nullable=True))
    op.add_column("community_topics", sa.Column("telegram_history_max_message_id", sa.BigInteger(), nullable=True))
    op.add_column("community_topics", sa.Column("telegram_history_synced_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column(
        "community_topics",
        sa.Column("telegram_history_complete", sa.Boolean(), server_default=sa.text("false"), nullable=False),
    )


def downgrade() -> None:
    op.drop_column("community_topics", "telegram_history_complete")
    op.drop_column("community_topics", "telegram_history_synced_at")
    op.drop_column("community_topics", "telegram_history_max_message_id")
    op.drop_column("community_topics", "telegram_history_min_message_id")
    op.drop_index("ix_community_telegram_parts_deleted_at", table_name="community_telegram_parts")
    op.drop_column("community_telegram_parts", "deleted_at")
    op.drop_index("ix_community_messages_deleted_at", table_name="community_messages")
    op.drop_index("ix_community_messages_edited_at", table_name="community_messages")
    op.drop_column("community_messages", "deleted_at")
    op.drop_column("community_messages", "edited_at")
