"""Per-account notification switches for the Telegram group and its topics."""
from alembic import op
import sqlalchemy as sa

revision = "b1d3f5a7c9e0"
down_revision = "a0c2e4f6b8d0"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "community_notification_mutes",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("telegram_chat_id", sa.BigInteger(), nullable=False),
        sa.Column("topic_id", sa.BigInteger(), sa.ForeignKey("community_topics.id", ondelete="CASCADE"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("user_id", "topic_id", name="uq_community_notification_mutes_user_topic"),
    )
    for column in ("id", "user_id", "telegram_chat_id", "topic_id"):
        op.create_index(f"ix_community_notification_mutes_{column}", "community_notification_mutes", [column])
    op.create_index("uq_community_notification_mutes_user_group", "community_notification_mutes", ["user_id", "telegram_chat_id"], unique=True, postgresql_where=sa.text("topic_id IS NULL"))


def downgrade():
    op.drop_table("community_notification_mutes")
