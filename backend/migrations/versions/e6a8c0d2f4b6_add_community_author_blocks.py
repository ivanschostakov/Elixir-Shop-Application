"""Per-account community author blocks.

Revision ID: e6a8c0d2f4b6
Revises: d5f7a9c1e3b5
"""
from alembic import op
import sqlalchemy as sa

revision = "e6a8c0d2f4b6"
down_revision = "d5f7a9c1e3b5"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "community_author_blocks",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("author_id", sa.BigInteger(), sa.ForeignKey("community_authors.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("user_id", "author_id", name="uq_community_author_blocks_user_author"),
    )
    for column in ("id", "user_id", "author_id"):
        op.create_index(f"ix_community_author_blocks_{column}", "community_author_blocks", [column])


def downgrade():
    op.drop_table("community_author_blocks")
