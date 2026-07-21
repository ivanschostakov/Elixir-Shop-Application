"""add community notification outbox

Revision ID: c4f6a8b0d2e3
Revises: b3e5f7a9c1d2
Create Date: 2026-07-21 23:30:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "c4f6a8b0d2e3"
down_revision = "b3e5f7a9c1d2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "community_notification_events",
        sa.Column("message_id", sa.BigInteger(), nullable=False),
        sa.Column("attempts", sa.Integer(), server_default="0", nullable=False),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["message_id"], ["community_messages.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("message_id"),
    )
    op.create_index("ix_community_notification_events_id", "community_notification_events", ["id"])
    op.create_index("ix_community_notification_events_message_id", "community_notification_events", ["message_id"])
    op.create_index("ix_community_notification_events_next_attempt_at", "community_notification_events", ["next_attempt_at"])
    op.create_index("ix_community_notification_events_sent_at", "community_notification_events", ["sent_at"])


def downgrade() -> None:
    op.drop_table("community_notification_events")
