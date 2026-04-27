"""add final orders, payments and amocrm linkage

Revision ID: 8f7c3b2a1d4e
Revises: 4c8e2f6a1b9d
Create Date: 2026-04-22 18:45:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "8f7c3b2a1d4e"
down_revision: Union[str, Sequence[str], None] = "4c8e2f6a1b9d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("contact_id", sa.BigInteger(), nullable=True))
    op.create_index(op.f("ix_users_contact_id"), "users", ["contact_id"], unique=False)

    op.create_table(
        "orders",
        sa.Column("draft_id", sa.BigInteger(), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("delivery_address_id", sa.BigInteger(), nullable=False),
        sa.Column("recipient_id", sa.BigInteger(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("items_count", sa.Integer(), nullable=False),
        sa.Column("total_quantity", sa.Integer(), nullable=False),
        sa.Column("basket_subtotal", sa.Numeric(12, 2), nullable=False),
        sa.Column("delivery_total", sa.Numeric(12, 2), nullable=False),
        sa.Column("grand_total", sa.Numeric(12, 2), nullable=False),
        sa.Column("currency", sa.String(length=8), nullable=False),
        sa.Column("delivery_period_min", sa.Integer(), nullable=True),
        sa.Column("delivery_period_max", sa.Integer(), nullable=True),
        sa.Column("comment", sa.String(length=500), nullable=True),
        sa.Column("delivery_string", sa.String(length=500), nullable=True),
        sa.Column("selected_delivery_service", sa.String(length=32), nullable=False),
        sa.Column("selected_delivery_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("checkout_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("payment_method", sa.String(length=32), nullable=True),
        sa.Column("payment_provider", sa.String(length=64), nullable=True),
        sa.Column("payment_status", sa.String(length=32), nullable=False),
        sa.Column("payment_invoice_id", sa.String(length=128), nullable=True),
        sa.Column("payment_paid_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("payment_error", sa.String(length=500), nullable=True),
        sa.Column("amocrm_lead_id", sa.BigInteger(), nullable=True),
        sa.Column("delivery_created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("delivery_provider_ref", sa.String(length=128), nullable=True),
        sa.Column("yandex_request_id", sa.String(length=128), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("is_paid", sa.Boolean(), nullable=False),
        sa.Column("is_canceled", sa.Boolean(), nullable=False),
        sa.Column("is_shipped", sa.Boolean(), nullable=False),
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["delivery_address_id"], ["delivery_addresses.id"]),
        sa.ForeignKeyConstraint(["draft_id"], ["order_drafts.id"]),
        sa.ForeignKeyConstraint(["recipient_id"], ["delivery_recipients.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_orders_id"), "orders", ["id"], unique=False)
    op.create_index(op.f("ix_orders_draft_id"), "orders", ["draft_id"], unique=False)
    op.create_index(op.f("ix_orders_user_id"), "orders", ["user_id"], unique=False)
    op.create_index(op.f("ix_orders_delivery_address_id"), "orders", ["delivery_address_id"], unique=False)
    op.create_index(op.f("ix_orders_recipient_id"), "orders", ["recipient_id"], unique=False)
    op.create_index(op.f("ix_orders_status"), "orders", ["status"], unique=False)
    op.create_index(op.f("ix_orders_payment_status"), "orders", ["payment_status"], unique=False)
    op.create_index(op.f("ix_orders_payment_invoice_id"), "orders", ["payment_invoice_id"], unique=False)
    op.create_index(op.f("ix_orders_amocrm_lead_id"), "orders", ["amocrm_lead_id"], unique=False)

    op.create_table(
        "order_items",
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("order_id", sa.BigInteger(), nullable=False),
        sa.Column("product_id", sa.BigInteger(), nullable=False),
        sa.Column("variant_id", sa.BigInteger(), nullable=False),
        sa.Column("product_name", sa.String(length=200), nullable=False),
        sa.Column("product_sku", sa.String(length=64), nullable=False),
        sa.Column("variant_name", sa.String(length=200), nullable=False),
        sa.Column("variant_sku", sa.String(length=64), nullable=True),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("unit_price", sa.Numeric(12, 2), nullable=False),
        sa.Column("line_total", sa.Numeric(12, 2), nullable=False),
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["order_id"], ["orders.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_order_items_id"), "order_items", ["id"], unique=False)
    op.create_index(op.f("ix_order_items_user_id"), "order_items", ["user_id"], unique=False)
    op.create_index(op.f("ix_order_items_order_id"), "order_items", ["order_id"], unique=False)
    op.create_index(op.f("ix_order_items_product_id"), "order_items", ["product_id"], unique=False)
    op.create_index(op.f("ix_order_items_variant_id"), "order_items", ["variant_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_order_items_variant_id"), table_name="order_items")
    op.drop_index(op.f("ix_order_items_product_id"), table_name="order_items")
    op.drop_index(op.f("ix_order_items_order_id"), table_name="order_items")
    op.drop_index(op.f("ix_order_items_user_id"), table_name="order_items")
    op.drop_index(op.f("ix_order_items_id"), table_name="order_items")
    op.drop_table("order_items")

    op.drop_index(op.f("ix_orders_amocrm_lead_id"), table_name="orders")
    op.drop_index(op.f("ix_orders_payment_invoice_id"), table_name="orders")
    op.drop_index(op.f("ix_orders_payment_status"), table_name="orders")
    op.drop_index(op.f("ix_orders_status"), table_name="orders")
    op.drop_index(op.f("ix_orders_recipient_id"), table_name="orders")
    op.drop_index(op.f("ix_orders_delivery_address_id"), table_name="orders")
    op.drop_index(op.f("ix_orders_user_id"), table_name="orders")
    op.drop_index(op.f("ix_orders_draft_id"), table_name="orders")
    op.drop_index(op.f("ix_orders_id"), table_name="orders")
    op.drop_table("orders")

    op.drop_index(op.f("ix_users_contact_id"), table_name="users")
    op.drop_column("users", "contact_id")
