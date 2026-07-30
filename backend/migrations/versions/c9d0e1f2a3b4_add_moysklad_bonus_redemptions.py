"""add moysklad bonus redemption metadata

Revision ID: c9d0e1f2a3b4
Revises: b7c8d9e0f1a2
Create Date: 2026-07-30 15:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "c9d0e1f2a3b4"
down_revision: str | Sequence[str] | None = "b7c8d9e0f1a2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "order_benefit_applications",
        sa.Column("source_external_id", sa.String(length=128), nullable=True),
    )
    op.add_column(
        "order_benefit_applications",
        sa.Column("benefit_units", sa.Numeric(14, 2), nullable=True),
    )
    op.add_column(
        "order_benefit_applications",
        sa.Column("external_reference", sa.String(length=128), nullable=True),
    )
    op.create_index(
        op.f("ix_order_benefit_applications_source_external_id"),
        "order_benefit_applications",
        ["source_external_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_order_benefit_applications_external_reference"),
        "order_benefit_applications",
        ["external_reference"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_order_benefit_applications_external_reference"),
        table_name="order_benefit_applications",
    )
    op.drop_index(
        op.f("ix_order_benefit_applications_source_external_id"),
        table_name="order_benefit_applications",
    )
    op.drop_column("order_benefit_applications", "external_reference")
    op.drop_column("order_benefit_applications", "benefit_units")
    op.drop_column("order_benefit_applications", "source_external_id")
