"""add community reaction delivery outbox

Revision ID: e7f8a9b0c1d2
Revises: d6e7f8a9b0c1
Create Date: 2026-07-24 17:30:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "e7f8a9b0c1d2"
down_revision = "d6e7f8a9b0c1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "community_reactions",
        sa.Column("delivery_status", sa.String(length=24), server_default="queued", nullable=False),
    )
    op.add_column(
        "community_reactions",
        sa.Column("delivery_error", sa.Text(), nullable=True),
    )
    op.add_column(
        "community_reactions",
        sa.Column("delivery_attempts", sa.Integer(), server_default="0", nullable=False),
    )
    op.add_column(
        "community_reactions",
        sa.Column("next_delivery_attempt_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.execute(
        """
        UPDATE community_reactions
        SET delivery_status = CASE
            WHEN telegram_message_id IS NOT NULL THEN 'sent'
            ELSE 'queued'
        END
        """
    )
    op.create_index(
        "ix_community_reactions_delivery_status",
        "community_reactions",
        ["delivery_status"],
    )
    op.create_index(
        "ix_community_reactions_next_delivery_attempt_at",
        "community_reactions",
        ["next_delivery_attempt_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_community_reactions_next_delivery_attempt_at",
        table_name="community_reactions",
    )
    op.drop_index(
        "ix_community_reactions_delivery_status",
        table_name="community_reactions",
    )
    op.drop_column("community_reactions", "next_delivery_attempt_at")
    op.drop_column("community_reactions", "delivery_attempts")
    op.drop_column("community_reactions", "delivery_error")
    op.drop_column("community_reactions", "delivery_status")
