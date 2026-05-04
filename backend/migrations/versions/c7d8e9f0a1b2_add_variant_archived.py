"""add variant archived flag

Revision ID: c7d8e9f0a1b2
Revises: b6c3d2e4f5a6
Create Date: 2026-05-04 15:15:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "c7d8e9f0a1b2"
down_revision: Union[str, Sequence[str], None] = "b6c3d2e4f5a6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _column_names(inspector: sa.Inspector, table_name: str) -> set[str]:
    return {column["name"] for column in inspector.get_columns(table_name)}


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table("variants"):
        return

    columns = _column_names(inspector, "variants")
    if "archived" not in columns:
        op.add_column(
            "variants",
            sa.Column("archived", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table("variants"):
        return

    columns = _column_names(inspector, "variants")
    if "archived" in columns:
        op.drop_column("variants", "archived")
