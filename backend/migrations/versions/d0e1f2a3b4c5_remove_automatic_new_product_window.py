"""remove automatic new product window

Revision ID: d0e1f2a3b4c5
Revises: c9d0e1f2a3b4
Create Date: 2026-07-30 16:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "d0e1f2a3b4c5"
down_revision: str | Sequence[str] | None = "c9d0e1f2a3b4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint(
        "ck_catalog_settings_new_product_days_range",
        "catalog_settings",
        type_="check",
    )
    op.drop_column("catalog_settings", "new_product_days")


def downgrade() -> None:
    op.add_column(
        "catalog_settings",
        sa.Column(
            "new_product_days",
            sa.Integer(),
            server_default=sa.text("30"),
            nullable=False,
        ),
    )
    op.create_check_constraint(
        "ck_catalog_settings_new_product_days_range",
        "catalog_settings",
        "new_product_days >= 0 AND new_product_days <= 3650",
    )
