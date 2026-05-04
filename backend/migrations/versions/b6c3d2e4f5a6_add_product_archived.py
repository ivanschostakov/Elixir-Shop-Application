"""add product archived flag

Revision ID: b6c3d2e4f5a6
Revises: 8d2f3b4c5e6a
Create Date: 2026-05-04 14:30:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "b6c3d2e4f5a6"
down_revision: Union[str, Sequence[str], None] = "8d2f3b4c5e6a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _column_names(inspector: sa.Inspector, table_name: str) -> set[str]:
    return {column["name"] for column in inspector.get_columns(table_name)}


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table("products"):
        return

    columns = _column_names(inspector, "products")
    if "archived" not in columns:
        op.add_column(
            "products",
            sa.Column("archived", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table("products"):
        return

    columns = _column_names(inspector, "products")
    if "archived" in columns:
        op.drop_column("products", "archived")
