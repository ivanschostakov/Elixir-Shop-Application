"""add catalog merchandising

Revision ID: b7c8d9e0f1a2
Revises: a1c2e3f4b5d6, a9c8e7f6b5d4
Create Date: 2026-07-30 12:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "b7c8d9e0f1a2"
down_revision: str | Sequence[str] | None = ("a1c2e3f4b5d6", "a9c8e7f6b5d4")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "catalog_settings",
        sa.Column("new_product_days", sa.Integer(), server_default=sa.text("30"), nullable=False),
    )
    op.create_check_constraint(
        "ck_catalog_settings_new_product_days_range",
        "catalog_settings",
        "new_product_days >= 0 AND new_product_days <= 3650",
    )
    op.add_column(
        "products",
        sa.Column("is_new_manual", sa.Boolean(), server_default=sa.text("false"), nullable=False),
    )
    op.add_column(
        "products",
        sa.Column("discount_percent", sa.Numeric(5, 2), server_default=sa.text("0.00"), nullable=False),
    )
    op.create_check_constraint(
        "ck_products_discount_percent_range",
        "products",
        "discount_percent >= 0 AND discount_percent <= 100",
    )
    op.add_column(
        "product_categories",
        sa.Column("discount_percent", sa.Numeric(5, 2), server_default=sa.text("0.00"), nullable=False),
    )
    op.create_check_constraint(
        "ck_product_categories_discount_percent_range",
        "product_categories",
        "discount_percent >= 0 AND discount_percent <= 100",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_product_categories_discount_percent_range",
        "product_categories",
        type_="check",
    )
    op.drop_column("product_categories", "discount_percent")
    op.drop_constraint("ck_products_discount_percent_range", "products", type_="check")
    op.drop_column("products", "discount_percent")
    op.drop_column("products", "is_new_manual")
    op.drop_constraint(
        "ck_catalog_settings_new_product_days_range",
        "catalog_settings",
        type_="check",
    )
    op.drop_column("catalog_settings", "new_product_days")
