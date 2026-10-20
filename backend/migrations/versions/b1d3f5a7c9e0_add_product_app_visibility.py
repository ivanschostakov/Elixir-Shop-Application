"""Add independently managed product visibility in the customer storefront.

Revision ID: b1d3f5a7c9e0
Revises: a0c2e4f6b8d0
Create Date: 2026-10-20
"""

from typing import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "b1d3f5a7c9e0"
down_revision: str | Sequence[str] | None = "a0c2e4f6b8d0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "products",
        sa.Column(
            "is_visible_in_app",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
    )


def downgrade() -> None:
    op.drop_column("products", "is_visible_in_app")
