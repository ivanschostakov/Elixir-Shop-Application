"""add community message reactions

Revision ID: b3e5f7a9c1d2
Revises: a2d4f6b8c0e1
Create Date: 2026-07-21 21:30:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "b3e5f7a9c1d2"
down_revision = "a2d4f6b8c0e1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "community_reactions",
        sa.Column("message_id", sa.BigInteger(), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("emoji", sa.String(length=16), nullable=False),
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["message_id"], ["community_messages.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("message_id", "user_id", "emoji", name="uq_community_reactions_message_user_emoji"),
    )
    op.create_index("ix_community_reactions_id", "community_reactions", ["id"])
    op.create_index("ix_community_reactions_message_id", "community_reactions", ["message_id"])
    op.create_index("ix_community_reactions_user_id", "community_reactions", ["user_id"])


def downgrade() -> None:
    op.drop_table("community_reactions")
