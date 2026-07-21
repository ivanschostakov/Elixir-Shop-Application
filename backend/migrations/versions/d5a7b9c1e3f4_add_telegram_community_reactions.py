"""add telegram community reactions

Revision ID: d5a7b9c1e3f4
Revises: c4f6a8b0d2e3
Create Date: 2026-07-21 23:55:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "d5a7b9c1e3f4"
down_revision = "c4f6a8b0d2e3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "community_telegram_reactions",
        sa.Column("message_id", sa.BigInteger(), nullable=False),
        sa.Column("telegram_chat_id", sa.BigInteger(), nullable=False),
        sa.Column("telegram_message_id", sa.BigInteger(), nullable=False),
        sa.Column("actor_key", sa.String(length=96), nullable=False),
        sa.Column("emoji", sa.String(length=32), nullable=False),
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["message_id"], ["community_messages.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "telegram_chat_id",
            "telegram_message_id",
            "actor_key",
            "emoji",
            name="uq_community_telegram_reactions_message_actor_emoji",
        ),
    )
    op.create_index("ix_community_telegram_reactions_id", "community_telegram_reactions", ["id"])
    op.create_index(
        "ix_community_telegram_reactions_message_id",
        "community_telegram_reactions",
        ["message_id"],
    )

    op.create_table(
        "community_telegram_reaction_counts",
        sa.Column("message_id", sa.BigInteger(), nullable=False),
        sa.Column("telegram_chat_id", sa.BigInteger(), nullable=False),
        sa.Column("telegram_message_id", sa.BigInteger(), nullable=False),
        sa.Column("emoji", sa.String(length=32), nullable=False),
        sa.Column("total_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["message_id"], ["community_messages.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "telegram_chat_id",
            "telegram_message_id",
            "emoji",
            name="uq_community_telegram_reaction_counts_message_emoji",
        ),
    )
    op.create_index("ix_community_telegram_reaction_counts_id", "community_telegram_reaction_counts", ["id"])
    op.create_index(
        "ix_community_telegram_reaction_counts_message_id",
        "community_telegram_reaction_counts",
        ["message_id"],
    )


def downgrade() -> None:
    op.drop_table("community_telegram_reaction_counts")
    op.drop_table("community_telegram_reactions")
