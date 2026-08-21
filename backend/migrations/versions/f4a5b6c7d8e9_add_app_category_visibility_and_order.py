"""add app category visibility and order

Revision ID: f4a5b6c7d8e9
Revises: e1a2b3c4d5f6
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "f4a5b6c7d8e9"
down_revision: str | Sequence[str] | None = "e1a2b3c4d5f6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "product_categories",
        sa.Column(
            "is_visible_in_app",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
    )
    op.add_column(
        "product_categories",
        sa.Column(
            "app_display_order",
            sa.Integer(),
            server_default=sa.text("10000"),
            nullable=False,
        ),
    )
    op.create_check_constraint(
        "ck_product_categories_app_display_order_nonnegative",
        "product_categories",
        "app_display_order >= 0",
    )
    op.execute(
        """
        WITH ordered_categories AS (
            SELECT
                id,
                row_number() OVER (ORDER BY lower(name), id) * 10 AS display_order
            FROM product_categories
        )
        UPDATE product_categories AS category
        SET app_display_order = ordered_categories.display_order
        FROM ordered_categories
        WHERE category.id = ordered_categories.id
        """
    )
    op.create_index(
        "ix_product_categories_is_visible_in_app",
        "product_categories",
        ["is_visible_in_app"],
        unique=False,
    )
    op.create_index(
        "ix_product_categories_app_display_order",
        "product_categories",
        ["app_display_order"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_product_categories_app_display_order",
        table_name="product_categories",
    )
    op.drop_index(
        "ix_product_categories_is_visible_in_app",
        table_name="product_categories",
    )
    op.drop_constraint(
        "ck_product_categories_app_display_order_nonnegative",
        "product_categories",
        type_="check",
    )
    op.drop_column("product_categories", "app_display_order")
    op.drop_column("product_categories", "is_visible_in_app")
