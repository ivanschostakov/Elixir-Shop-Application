"""make product text fields unbounded

Revision ID: 8d2f3b4c5e6a
Revises: 7b4c2a9e1f0d
Create Date: 2026-05-04 13:55:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "8d2f3b4c5e6a"
down_revision: Union[str, Sequence[str], None] = "7b4c2a9e1f0d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "products",
        "description",
        existing_type=sa.String(length=5000),
        type_=sa.Text(),
        existing_nullable=True,
    )
    op.alter_column(
        "products",
        "usage",
        existing_type=sa.String(length=2000),
        type_=sa.Text(),
        existing_nullable=True,
    )
    op.alter_column(
        "products",
        "expiration",
        existing_type=sa.String(length=1000),
        type_=sa.Text(),
        existing_nullable=True,
    )


def downgrade() -> None:
    op.alter_column(
        "products",
        "description",
        existing_type=sa.Text(),
        type_=sa.String(length=5000),
        existing_nullable=True,
    )
    op.alter_column(
        "products",
        "usage",
        existing_type=sa.Text(),
        type_=sa.String(length=2000),
        existing_nullable=True,
    )
    op.alter_column(
        "products",
        "expiration",
        existing_type=sa.Text(),
        type_=sa.String(length=1000),
        existing_nullable=True,
    )
