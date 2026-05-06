"""add product category archived flag

Revision ID: ed4b7c3a9f12
Revises: e9a4f2c8d7b1
Create Date: 2026-05-06 20:35:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "ed4b7c3a9f12"
down_revision: Union[str, Sequence[str], None] = "e9a4f2c8d7b1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _column_names(inspector: sa.Inspector, table_name: str) -> set[str]:
    return {column["name"] for column in inspector.get_columns(table_name)}


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table("product_categories"):
        return

    columns = _column_names(inspector, "product_categories")
    if "archived" not in columns:
        op.add_column(
            "product_categories",
            sa.Column("archived", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table("product_categories"):
        return

    columns = _column_names(inspector, "product_categories")
    if "archived" in columns:
        op.drop_column("product_categories", "archived")
