"""remove delivery address string limits

Revision ID: 6c1f0b8e9a72
Revises: e3a1d9c4b7f0, e7b8c9d0a1f2
Create Date: 2026-05-01 19:10:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "6c1f0b8e9a72"
down_revision: Union[str, Sequence[str], None] = ("e3a1d9c4b7f0", "e7b8c9d0a1f2")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "delivery_addresses",
        "name",
        existing_type=sa.String(length=100),
        type_=sa.Text(),
        existing_nullable=False,
    )
    op.alter_column(
        "delivery_addresses",
        "full_address",
        existing_type=sa.String(length=255),
        type_=sa.Text(),
        existing_nullable=False,
    )
    op.alter_column(
        "delivery_addresses",
        "details",
        existing_type=sa.String(length=255),
        type_=sa.Text(),
        existing_nullable=True,
    )
    op.alter_column(
        "delivery_addresses",
        "city",
        existing_type=sa.String(length=120),
        type_=sa.Text(),
        existing_nullable=True,
    )
    op.alter_column(
        "delivery_addresses",
        "postal_code",
        existing_type=sa.String(length=32),
        type_=sa.Text(),
        existing_nullable=True,
    )
    op.alter_column(
        "delivery_addresses",
        "provider_reference",
        existing_type=sa.String(length=128),
        type_=sa.Text(),
        existing_nullable=True,
    )


def downgrade() -> None:
    op.alter_column(
        "delivery_addresses",
        "provider_reference",
        existing_type=sa.Text(),
        type_=sa.String(length=128),
        existing_nullable=True,
    )
    op.alter_column(
        "delivery_addresses",
        "postal_code",
        existing_type=sa.Text(),
        type_=sa.String(length=32),
        existing_nullable=True,
    )
    op.alter_column(
        "delivery_addresses",
        "city",
        existing_type=sa.Text(),
        type_=sa.String(length=120),
        existing_nullable=True,
    )
    op.alter_column(
        "delivery_addresses",
        "details",
        existing_type=sa.Text(),
        type_=sa.String(length=255),
        existing_nullable=True,
    )
    op.alter_column(
        "delivery_addresses",
        "full_address",
        existing_type=sa.Text(),
        type_=sa.String(length=255),
        existing_nullable=False,
    )
    op.alter_column(
        "delivery_addresses",
        "name",
        existing_type=sa.Text(),
        type_=sa.String(length=100),
        existing_nullable=False,
    )
