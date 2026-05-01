"""add review attachments table

Revision ID: f4e280cf3b2f
Revises: 5f2d1e8a9c44
Create Date: 2026-05-01 03:00:45.949501

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f4e280cf3b2f'
down_revision: Union[str, Sequence[str], None] = '5f2d1e8a9c44'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "review_attachments",
        sa.Column("review_id", sa.BigInteger(), nullable=False),
        sa.Column("filename", sa.String(length=128), nullable=False),
        sa.Column("mime_type", sa.String(length=100), nullable=True),
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["review_id"], ["reviews.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_review_attachments_id"), "review_attachments", ["id"], unique=False)
    op.create_index(
        op.f("ix_review_attachments_review_id"),
        "review_attachments",
        ["review_id"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f("ix_review_attachments_review_id"), table_name="review_attachments")
    op.drop_index(op.f("ix_review_attachments_id"), table_name="review_attachments")
    op.drop_table("review_attachments")
