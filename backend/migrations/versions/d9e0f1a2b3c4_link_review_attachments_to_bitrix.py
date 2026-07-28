"""link review attachments to Bitrix files

Revision ID: d9e0f1a2b3c4
Revises: c8d9e0f1a2b3
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "d9e0f1a2b3c4"
down_revision: str | Sequence[str] | None = "c8d9e0f1a2b3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "review_attachments",
        sa.Column("website_file_id", sa.BigInteger(), nullable=True),
    )
    op.create_index(
        op.f("ix_review_attachments_website_file_id"),
        "review_attachments",
        ["website_file_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_review_attachments_website_file_id"),
        table_name="review_attachments",
    )
    op.drop_column("review_attachments", "website_file_id")
