"""Community message reports and moderation queue."""
from alembic import op
import sqlalchemy as sa

revision = "f7b9d1e3a5c7"
down_revision = "e6a8c0d2f4b6"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "community_reports",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("reporter_id", sa.BigInteger(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("message_id", sa.BigInteger(), sa.ForeignKey("community_messages.id", ondelete="CASCADE"), nullable=False),
        sa.Column("reason", sa.String(32), nullable=False),
        sa.Column("details", sa.Text(), server_default="", nullable=False),
        sa.Column("status", sa.String(16), server_default="pending", nullable=False),
        sa.Column("moderator_id", sa.BigInteger(), sa.ForeignKey("admins.user_id", ondelete="SET NULL")),
        sa.Column("moderation_note", sa.Text(), server_default="", nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("reporter_id", "message_id", name="uq_community_reports_reporter_message"),
        sa.CheckConstraint("status IN ('pending', 'dismissed', 'removed')", name="ck_community_reports_status"),
        sa.CheckConstraint("reason IN ('spam', 'harassment', 'dangerous_content', 'inappropriate_content', 'other')", name="ck_community_reports_reason"),
    )
    for column in ("id", "reporter_id", "message_id", "status"):
        op.create_index(f"ix_community_reports_{column}", "community_reports", [column])


def downgrade():
    op.drop_table("community_reports")
