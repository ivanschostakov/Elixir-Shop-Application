"""create delivery addresses and order draft tables

Revision ID: bd9a1c9f7d21
Revises: aa833c6f3f6f
Create Date: 2026-04-20 18:45:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "bd9a1c9f7d21"
down_revision: Union[str, Sequence[str], None] = "aa833c6f3f6f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


DELIVERY_MODE_ENUM = postgresql.ENUM("door", "pickup", name="delivery_mode_enum", create_type=False)
COUNTRY_CODE_ENUM = postgresql.ENUM(
    "RU",
    "BY",
    "KZ",
    "AZ",
    "MD",
    "AM",
    "UZ",
    "KG",
    "GE",
    "MN",
    "CN",
    "JP",
    "RS",
    "IL",
    "AE",
    "IN",
    "BD",
    "VN",
    "TH",
    "ID",
    "US",
    name="country_code_enum",
    create_type=False,
)
DELIVERY_PROVIDER_ENUM = postgresql.ENUM("YANDEX", "CDEK", name="delivery_provider_enum", create_type=False)


def _create_delivery_mode_enum() -> None:
    bind = op.get_bind()
    postgresql.ENUM("door", "pickup", name="delivery_mode_enum").create(bind, checkfirst=True)


def _drop_delivery_mode_enum() -> None:
    bind = op.get_bind()
    postgresql.ENUM("door", "pickup", name="delivery_mode_enum").drop(bind, checkfirst=True)


def upgrade() -> None:
    _create_delivery_mode_enum()

    op.create_table(
        "delivery_addresses",
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("mode", DELIVERY_MODE_ENUM, nullable=False),
        sa.Column("provider", DELIVERY_PROVIDER_ENUM, nullable=False),
        sa.Column("country_code", COUNTRY_CODE_ENUM, nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("full_address", sa.String(length=255), nullable=False),
        sa.Column("details", sa.String(length=255), nullable=True),
        sa.Column("city", sa.String(length=120), nullable=True),
        sa.Column("postal_code", sa.String(length=32), nullable=True),
        sa.Column("latitude", sa.Float(), nullable=False),
        sa.Column("longitude", sa.Float(), nullable=False),
        sa.Column("provider_reference", sa.String(length=128), nullable=True),
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_delivery_addresses_id"), "delivery_addresses", ["id"], unique=False)
    op.create_index(op.f("ix_delivery_addresses_user_id"), "delivery_addresses", ["user_id"], unique=False)
    op.create_index(op.f("ix_delivery_addresses_mode"), "delivery_addresses", ["mode"], unique=False)
    op.create_index(op.f("ix_delivery_addresses_provider"), "delivery_addresses", ["provider"], unique=False)
    op.create_index(op.f("ix_delivery_addresses_country_code"), "delivery_addresses", ["country_code"], unique=False)
    op.create_index(op.f("ix_delivery_addresses_provider_reference"), "delivery_addresses", ["provider_reference"], unique=False)

    op.create_table(
        "order_drafts",
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("delivery_address_id", sa.BigInteger(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="draft"),
        sa.Column("items_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_quantity", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("basket_subtotal", sa.Numeric(12, 2), nullable=False, server_default="0.00"),
        sa.Column("delivery_total", sa.Numeric(12, 2), nullable=False, server_default="0.00"),
        sa.Column("grand_total", sa.Numeric(12, 2), nullable=False, server_default="0.00"),
        sa.Column("currency", sa.String(length=8), nullable=False, server_default="RUB"),
        sa.Column("delivery_period_min", sa.Integer(), nullable=True),
        sa.Column("delivery_period_max", sa.Integer(), nullable=True),
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["delivery_address_id"], ["delivery_addresses.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_order_drafts_id"), "order_drafts", ["id"], unique=False)
    op.create_index(op.f("ix_order_drafts_user_id"), "order_drafts", ["user_id"], unique=False)
    op.create_index(op.f("ix_order_drafts_delivery_address_id"), "order_drafts", ["delivery_address_id"], unique=False)
    op.create_index(op.f("ix_order_drafts_status"), "order_drafts", ["status"], unique=False)

    op.create_table(
        "order_draft_items",
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("draft_id", sa.BigInteger(), nullable=False),
        sa.Column("product_id", sa.BigInteger(), nullable=False),
        sa.Column("variant_id", sa.BigInteger(), nullable=False),
        sa.Column("product_name", sa.String(length=200), nullable=False),
        sa.Column("product_sku", sa.String(length=64), nullable=False),
        sa.Column("variant_name", sa.String(length=200), nullable=False),
        sa.Column("variant_sku", sa.String(length=64), nullable=True),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("unit_price", sa.Numeric(12, 2), nullable=False, server_default="0.00"),
        sa.Column("line_total", sa.Numeric(12, 2), nullable=False, server_default="0.00"),
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["draft_id"], ["order_drafts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_order_draft_items_id"), "order_draft_items", ["id"], unique=False)
    op.create_index(op.f("ix_order_draft_items_user_id"), "order_draft_items", ["user_id"], unique=False)
    op.create_index(op.f("ix_order_draft_items_draft_id"), "order_draft_items", ["draft_id"], unique=False)
    op.create_index(op.f("ix_order_draft_items_product_id"), "order_draft_items", ["product_id"], unique=False)
    op.create_index(op.f("ix_order_draft_items_variant_id"), "order_draft_items", ["variant_id"], unique=False)

    op.alter_column("order_draft_items", "unit_price", server_default=None)
    op.alter_column("order_draft_items", "line_total", server_default=None)
    op.alter_column("order_drafts", "status", server_default=None)
    op.alter_column("order_drafts", "items_count", server_default=None)
    op.alter_column("order_drafts", "total_quantity", server_default=None)
    op.alter_column("order_drafts", "basket_subtotal", server_default=None)
    op.alter_column("order_drafts", "delivery_total", server_default=None)
    op.alter_column("order_drafts", "grand_total", server_default=None)
    op.alter_column("order_drafts", "currency", server_default=None)


def downgrade() -> None:
    op.drop_index(op.f("ix_order_draft_items_variant_id"), table_name="order_draft_items")
    op.drop_index(op.f("ix_order_draft_items_product_id"), table_name="order_draft_items")
    op.drop_index(op.f("ix_order_draft_items_draft_id"), table_name="order_draft_items")
    op.drop_index(op.f("ix_order_draft_items_user_id"), table_name="order_draft_items")
    op.drop_index(op.f("ix_order_draft_items_id"), table_name="order_draft_items")
    op.drop_table("order_draft_items")

    op.drop_index(op.f("ix_order_drafts_status"), table_name="order_drafts")
    op.drop_index(op.f("ix_order_drafts_delivery_address_id"), table_name="order_drafts")
    op.drop_index(op.f("ix_order_drafts_user_id"), table_name="order_drafts")
    op.drop_index(op.f("ix_order_drafts_id"), table_name="order_drafts")
    op.drop_table("order_drafts")

    op.drop_index(op.f("ix_delivery_addresses_provider_reference"), table_name="delivery_addresses")
    op.drop_index(op.f("ix_delivery_addresses_country_code"), table_name="delivery_addresses")
    op.drop_index(op.f("ix_delivery_addresses_provider"), table_name="delivery_addresses")
    op.drop_index(op.f("ix_delivery_addresses_mode"), table_name="delivery_addresses")
    op.drop_index(op.f("ix_delivery_addresses_user_id"), table_name="delivery_addresses")
    op.drop_index(op.f("ix_delivery_addresses_id"), table_name="delivery_addresses")
    op.drop_table("delivery_addresses")

    _drop_delivery_mode_enum()
