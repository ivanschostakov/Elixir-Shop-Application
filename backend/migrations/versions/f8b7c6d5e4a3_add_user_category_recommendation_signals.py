"""add user category recommendation signals

Revision ID: f8b7c6d5e4a3
Revises: f2a1c9d4b8e7
Create Date: 2026-04-24 00:35:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "f8b7c6d5e4a3"
down_revision: Union[str, Sequence[str], None] = "f2a1c9d4b8e7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "user_category_recommendation_signals",
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("category_id", sa.BigInteger(), nullable=False),
        sa.Column("view_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("last_viewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["category_id"], ["product_categories.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_id",
            "category_id",
            name="uq_user_category_recommendation_signals_user_id_category_id",
        ),
    )
    op.create_index(
        op.f("ix_user_category_recommendation_signals_category_id"),
        "user_category_recommendation_signals",
        ["category_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_user_category_recommendation_signals_id"),
        "user_category_recommendation_signals",
        ["id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_user_category_recommendation_signals_user_id"),
        "user_category_recommendation_signals",
        ["user_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_user_category_recommendation_signals_user_id"),
        table_name="user_category_recommendation_signals",
    )
    op.drop_index(
        op.f("ix_user_category_recommendation_signals_id"),
        table_name="user_category_recommendation_signals",
    )
    op.drop_index(
        op.f("ix_user_category_recommendation_signals_category_id"),
        table_name="user_category_recommendation_signals",
    )
    op.drop_table("user_category_recommendation_signals")
