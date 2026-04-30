"""create reviews table if missing

Revision ID: c4f1a7d9e2b3
Revises: 91b4a6f2d8c1
Create Date: 2026-04-29 13:35:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "c4f1a7d9e2b3"
down_revision: Union[str, Sequence[str], None] = "91b4a6f2d8c1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if inspector.has_table("reviews"):
        return

    op.create_table(
        "reviews",
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("product_id", sa.BigInteger(), nullable=False),
        sa.Column("value", sa.Integer(), nullable=False),
        sa.Column("text", sa.String(length=1000), nullable=True),
        sa.Column("answer", sa.String(length=1000), nullable=True),
        sa.Column("likes", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("dislikes", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("moderated", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint("value >= 0 AND value <= 5", name="check_review_value_0_5"),
        sa.CheckConstraint("likes >= 0", name="check_likes_non_negative"),
        sa.CheckConstraint("dislikes >= 0", name="check_dislikes_non_negative"),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_reviews_id"), "reviews", ["id"], unique=False)
    op.create_index(op.f("ix_reviews_product_id"), "reviews", ["product_id"], unique=False)
    op.create_index(op.f("ix_reviews_user_id"), "reviews", ["user_id"], unique=False)


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if not inspector.has_table("reviews"):
        return

    op.drop_index(op.f("ix_reviews_user_id"), table_name="reviews")
    op.drop_index(op.f("ix_reviews_product_id"), table_name="reviews")
    op.drop_index(op.f("ix_reviews_id"), table_name="reviews")
    op.drop_table("reviews")
