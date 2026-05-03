"""add checkout fields to baskets

Revision ID: 5bc7d4a8f901
Revises: f1a2b3c4d5e6
Create Date: 2026-05-03 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "5bc7d4a8f901"
down_revision: Union[str, None] = "f1a2b3c4d5e6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("baskets", sa.Column("delivery_address_id", sa.BigInteger(), nullable=True))
    op.add_column("baskets", sa.Column("recipient_id", sa.BigInteger(), nullable=True))
    op.add_column("baskets", sa.Column("delivery_total", sa.Numeric(12, 2), server_default=sa.text("0.00"), nullable=False))
    op.add_column("baskets", sa.Column("currency", sa.String(length=8), server_default=sa.text("'RUB'"), nullable=False))
    op.add_column("baskets", sa.Column("delivery_period_min", sa.Integer(), nullable=True))
    op.add_column("baskets", sa.Column("delivery_period_max", sa.Integer(), nullable=True))
    op.create_index(op.f("ix_baskets_delivery_address_id"), "baskets", ["delivery_address_id"], unique=False)
    op.create_index(op.f("ix_baskets_recipient_id"), "baskets", ["recipient_id"], unique=False)
    op.create_foreign_key("fk_baskets_delivery_address_id_delivery_addresses", "baskets", "delivery_addresses", ["delivery_address_id"], ["id"])
    op.create_foreign_key("fk_baskets_recipient_id_delivery_recipients", "baskets", "delivery_recipients", ["recipient_id"], ["id"])


def downgrade() -> None:
    op.drop_constraint("fk_baskets_recipient_id_delivery_recipients", "baskets", type_="foreignkey")
    op.drop_constraint("fk_baskets_delivery_address_id_delivery_addresses", "baskets", type_="foreignkey")
    op.drop_index(op.f("ix_baskets_recipient_id"), table_name="baskets")
    op.drop_index(op.f("ix_baskets_delivery_address_id"), table_name="baskets")
    op.drop_column("baskets", "delivery_period_max")
    op.drop_column("baskets", "delivery_period_min")
    op.drop_column("baskets", "currency")
    op.drop_column("baskets", "delivery_total")
    op.drop_column("baskets", "recipient_id")
    op.drop_column("baskets", "delivery_address_id")
