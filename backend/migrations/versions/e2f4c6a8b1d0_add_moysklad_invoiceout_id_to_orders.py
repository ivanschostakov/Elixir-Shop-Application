"""add moysklad invoiceout id to orders

Revision ID: e2f4c6a8b1d0
Revises: c0d4e5f6a7b8
Create Date: 2026-05-23 19:55:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "e2f4c6a8b1d0"
down_revision = "c0d4e5f6a7b8"
branch_labels = None
depends_on = None


def _table_exists(inspector: sa.Inspector, table_name: str) -> bool:
    return table_name in inspector.get_table_names()


def _column_names(inspector: sa.Inspector, table_name: str) -> set[str]:
    return {column["name"] for column in inspector.get_columns(table_name)}


def _index_names(inspector: sa.Inspector, table_name: str) -> set[str | None]:
    return {index["name"] for index in inspector.get_indexes(table_name)}


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not _table_exists(inspector, "orders"): return
    order_columns = _column_names(inspector, "orders")
    if "moysklad_invoiceout_id" not in order_columns:
        op.add_column("orders", sa.Column("moysklad_invoiceout_id", postgresql.UUID(as_uuid=True), nullable=True))
        inspector = sa.inspect(bind)
    order_indexes = _index_names(inspector, "orders")
    if "ix_orders_moysklad_invoiceout_id" not in order_indexes:
        op.create_index("ix_orders_moysklad_invoiceout_id", "orders", ["moysklad_invoiceout_id"], unique=False)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not _table_exists(inspector, "orders"): return
    order_indexes = _index_names(inspector, "orders")
    if "ix_orders_moysklad_invoiceout_id" in order_indexes:
        op.drop_index("ix_orders_moysklad_invoiceout_id", table_name="orders")
    order_columns = _column_names(inspector, "orders")
    if "moysklad_invoiceout_id" in order_columns:
        op.drop_column("orders", "moysklad_invoiceout_id")
