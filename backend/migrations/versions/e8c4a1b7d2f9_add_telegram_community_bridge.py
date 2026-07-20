"""add telegram community bridge

Revision ID: e8c4a1b7d2f9
Revises: a7b8c9d0e1f2
Create Date: 2026-07-21 12:00:00.000000
"""

from alembic import op
import sqlalchemy as sa

revision = "e8c4a1b7d2f9"
down_revision = "a7b8c9d0e1f2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "community_authors",
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column("telegram_peer_id", sa.BigInteger(), nullable=False),
        sa.Column("app_user_id", sa.BigInteger(), nullable=True),
        sa.Column("full_name", sa.String(length=255), nullable=False),
        sa.Column("avatar_file_id", sa.String(length=255), nullable=True),
        sa.Column("avatar_local_filename", sa.String(length=255), nullable=True),
        sa.Column("avatar_refreshed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["app_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("kind", "telegram_peer_id", name="uq_community_authors_kind_peer"),
    )
    op.create_index("ix_community_authors_id", "community_authors", ["id"])
    op.create_index("ix_community_authors_telegram_peer_id", "community_authors", ["telegram_peer_id"])
    op.create_index("ix_community_authors_app_user_id", "community_authors", ["app_user_id"])

    op.create_table(
        "community_topics",
        sa.Column("telegram_chat_id", sa.BigInteger(), nullable=False),
        sa.Column("telegram_thread_id", sa.BigInteger(), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("icon_color", sa.Integer(), nullable=True),
        sa.Column("icon_custom_emoji_id", sa.String(length=255), nullable=True),
        sa.Column("is_closed", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("is_hidden", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("last_message_id", sa.BigInteger(), nullable=True),
        sa.Column("last_message_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("telegram_chat_id", "telegram_thread_id", name="uq_community_topics_chat_thread"),
    )
    op.create_index("ix_community_topics_id", "community_topics", ["id"])
    op.create_index("ix_community_topics_telegram_chat_id", "community_topics", ["telegram_chat_id"])
    op.create_index("ix_community_topics_last_message_id", "community_topics", ["last_message_id"])
    op.create_index("ix_community_topics_last_message_at", "community_topics", ["last_message_at"])

    op.create_table(
        "community_messages",
        sa.Column("topic_id", sa.BigInteger(), nullable=False),
        sa.Column("author_id", sa.BigInteger(), nullable=True),
        sa.Column("app_user_id", sa.BigInteger(), nullable=True),
        sa.Column("reply_to_message_id", sa.BigInteger(), nullable=True),
        sa.Column("source", sa.String(length=16), nullable=False),
        sa.Column("client_id", sa.String(length=64), nullable=True),
        sa.Column("telegram_media_group_id", sa.String(length=128), nullable=True),
        sa.Column("text", sa.Text(), server_default="", nullable=False),
        sa.Column("unsupported_type", sa.String(length=64), nullable=True),
        sa.Column("delivery_status", sa.String(length=24), server_default="sent", nullable=False),
        sa.Column("delivery_error", sa.Text(), nullable=True),
        sa.Column("delivery_attempts", sa.Integer(), server_default="0", nullable=False),
        sa.Column("next_delivery_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["app_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["author_id"], ["community_authors.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["reply_to_message_id"], ["community_messages.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["topic_id"], ["community_topics.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("app_user_id", "client_id", name="uq_community_messages_user_client"),
    )
    for column in ("id", "topic_id", "author_id", "app_user_id", "reply_to_message_id", "telegram_media_group_id", "next_delivery_attempt_at", "sent_at"):
        op.create_index(f"ix_community_messages_{column}", "community_messages", [column])

    op.create_table(
        "community_attachments",
        sa.Column("message_id", sa.BigInteger(), nullable=False),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column("original_filename", sa.String(length=255), nullable=True),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("mime_type", sa.String(length=128), nullable=True),
        sa.Column("size_bytes", sa.BigInteger(), server_default="0", nullable=False),
        sa.Column("local_filename", sa.String(length=255), nullable=True),
        sa.Column("telegram_file_id", sa.String(length=255), nullable=True),
        sa.Column("telegram_file_unique_id", sa.String(length=255), nullable=True),
        sa.Column("telegram_message_id", sa.BigInteger(), nullable=True),
        sa.Column("status", sa.String(length=24), server_default="ready", nullable=False),
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["message_id"], ["community_messages.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_community_attachments_id", "community_attachments", ["id"])
    op.create_index("ix_community_attachments_message_id", "community_attachments", ["message_id"])

    op.create_table(
        "community_telegram_parts",
        sa.Column("message_id", sa.BigInteger(), nullable=False),
        sa.Column("telegram_chat_id", sa.BigInteger(), nullable=False),
        sa.Column("telegram_message_id", sa.BigInteger(), nullable=False),
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["message_id"], ["community_messages.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("telegram_chat_id", "telegram_message_id", name="uq_community_telegram_parts_chat_message"),
    )
    op.create_index("ix_community_telegram_parts_id", "community_telegram_parts", ["id"])
    op.create_index("ix_community_telegram_parts_message_id", "community_telegram_parts", ["message_id"])

    op.create_table(
        "community_topic_reads",
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("topic_id", sa.BigInteger(), nullable=False),
        sa.Column("last_read_message_id", sa.BigInteger(), nullable=True),
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["topic_id"], ["community_topics.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "topic_id", name="uq_community_topic_reads_user_topic"),
    )
    op.create_index("ix_community_topic_reads_id", "community_topic_reads", ["id"])
    op.create_index("ix_community_topic_reads_user_id", "community_topic_reads", ["user_id"])
    op.create_index("ix_community_topic_reads_topic_id", "community_topic_reads", ["topic_id"])


def downgrade() -> None:
    op.drop_table("community_topic_reads")
    op.drop_table("community_telegram_parts")
    op.drop_table("community_attachments")
    op.drop_table("community_messages")
    op.drop_table("community_topics")
    op.drop_table("community_authors")
