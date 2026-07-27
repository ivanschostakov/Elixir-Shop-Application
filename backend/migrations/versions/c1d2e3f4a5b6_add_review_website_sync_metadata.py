"""add review website sync metadata

Revision ID: c1d2e3f4a5b6
Revises: b0c1d2e3f4a5
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "c1d2e3f4a5b6"
down_revision: str | Sequence[str] | None = "b0c1d2e3f4a5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "reviews",
        sa.Column("sync_origin", sa.String(length=32), server_default=sa.text("'app'"), nullable=False),
    )
    op.add_column("reviews", sa.Column("website_review_id", sa.BigInteger(), nullable=True))
    op.add_column("reviews", sa.Column("website_updated_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index(op.f("ix_reviews_sync_origin"), "reviews", ["sync_origin"])
    op.create_index(op.f("ix_reviews_website_review_id"), "reviews", ["website_review_id"], unique=True)


def downgrade() -> None:
    op.drop_index(op.f("ix_reviews_website_review_id"), table_name="reviews")
    op.drop_index(op.f("ix_reviews_sync_origin"), table_name="reviews")
    op.drop_column("reviews", "website_updated_at")
    op.drop_column("reviews", "website_review_id")
    op.drop_column("reviews", "sync_origin")
