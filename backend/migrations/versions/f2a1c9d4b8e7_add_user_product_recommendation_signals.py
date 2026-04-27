"""add user product recommendation signals

Revision ID: f2a1c9d4b8e7
Revises: d5e8f1a3c9b2
Create Date: 2026-04-23 23:15:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "f2a1c9d4b8e7"
down_revision: Union[str, Sequence[str], None] = "d5e8f1a3c9b2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "user_product_recommendation_signals",
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("product_id", sa.BigInteger(), nullable=False),
        sa.Column("view_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("cart_quantity", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("purchase_quantity", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("last_viewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_carted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_purchased_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_id",
            "product_id",
            name="uq_user_product_recommendation_signals_user_id_product_id",
        ),
    )
    op.create_index(
        op.f("ix_user_product_recommendation_signals_id"),
        "user_product_recommendation_signals",
        ["id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_user_product_recommendation_signals_product_id"),
        "user_product_recommendation_signals",
        ["product_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_user_product_recommendation_signals_user_id"),
        "user_product_recommendation_signals",
        ["user_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_user_product_recommendation_signals_user_id"),
        table_name="user_product_recommendation_signals",
    )
    op.drop_index(
        op.f("ix_user_product_recommendation_signals_product_id"),
        table_name="user_product_recommendation_signals",
    )
    op.drop_index(
        op.f("ix_user_product_recommendation_signals_id"),
        table_name="user_product_recommendation_signals",
    )
    op.drop_table("user_product_recommendation_signals")
