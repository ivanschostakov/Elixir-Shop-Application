"""add catalog stock visibility settings

Revision ID: e3f4a5b6c7d8
Revises: d2e3f4a5b6c7
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "e3f4a5b6c7d8"
down_revision: str | Sequence[str] | None = "d2e3f4a5b6c7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "catalog_settings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column(
            "stock_reduction_enabled",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column(
            "stock_reduction",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("id = 1", name="ck_catalog_settings_singleton"),
        sa.CheckConstraint(
            "stock_reduction >= 0",
            name="ck_catalog_settings_stock_reduction_nonnegative",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.add_column(
        "products",
        sa.Column("stock_reduction_override", sa.Integer(), nullable=True),
    )
    op.create_check_constraint(
        "ck_products_stock_reduction_override_nonnegative",
        "products",
        "stock_reduction_override IS NULL OR stock_reduction_override >= 0",
    )
    op.execute(
        """
        INSERT INTO catalog_settings (
            id,
            stock_reduction_enabled,
            stock_reduction
        )
        VALUES (1, false, 0)
        """
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_products_stock_reduction_override_nonnegative",
        "products",
        type_="check",
    )
    op.drop_column("products", "stock_reduction_override")
    op.drop_table("catalog_settings")
