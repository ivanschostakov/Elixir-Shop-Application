"""add telegram topic sync metadata

Revision ID: f7c2a9d4e1b6
Revises: e8c4a1b7d2f9
Create Date: 2026-07-21 01:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "f7c2a9d4e1b6"
down_revision = "e8c4a1b7d2f9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "community_topics",
        sa.Column("is_pinned", sa.Boolean(), server_default=sa.text("false"), nullable=False),
    )
    op.add_column(
        "community_topics",
        sa.Column("is_deleted", sa.Boolean(), server_default=sa.text("false"), nullable=False),
    )
    op.add_column("community_topics", sa.Column("telegram_top_message_id", sa.BigInteger(), nullable=True))
    op.add_column("community_topics", sa.Column("telegram_creator_peer_id", sa.BigInteger(), nullable=True))
    op.add_column("community_topics", sa.Column("telegram_created_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("community_topics", sa.Column("telegram_synced_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("community_topics", "telegram_synced_at")
    op.drop_column("community_topics", "telegram_created_at")
    op.drop_column("community_topics", "telegram_creator_peer_id")
    op.drop_column("community_topics", "telegram_top_message_id")
    op.drop_column("community_topics", "is_deleted")
    op.drop_column("community_topics", "is_pinned")
