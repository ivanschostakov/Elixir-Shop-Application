"""add moysklad ids for users and orders

Revision ID: c0d4e5f6a7b8
Revises: b3f4e2a1c7d9
Create Date: 2026-05-23 13:20:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "c0d4e5f6a7b8"
down_revision = "b3f4e2a1c7d9"
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

    if _table_exists(inspector, "users"):
        user_columns = _column_names(inspector, "users")
        if "moysklad_counterparty_id" not in user_columns:
            op.add_column(
                "users",
                sa.Column("moysklad_counterparty_id", postgresql.UUID(as_uuid=True), nullable=True),
            )
            inspector = sa.inspect(bind)
        user_indexes = _index_names(inspector, "users")
        if "ix_users_moysklad_counterparty_id" not in user_indexes:
            op.create_index("ix_users_moysklad_counterparty_id", "users", ["moysklad_counterparty_id"], unique=False)

    if _table_exists(inspector, "orders"):
        order_columns = _column_names(inspector, "orders")
        if "moysklad_customerorder_id" not in order_columns:
            op.add_column(
                "orders",
                sa.Column("moysklad_customerorder_id", postgresql.UUID(as_uuid=True), nullable=True),
            )
            inspector = sa.inspect(bind)
        order_indexes = _index_names(inspector, "orders")
        if "ix_orders_moysklad_customerorder_id" not in order_indexes:
            op.create_index("ix_orders_moysklad_customerorder_id", "orders", ["moysklad_customerorder_id"], unique=False)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if _table_exists(inspector, "orders"):
        order_indexes = _index_names(inspector, "orders")
        if "ix_orders_moysklad_customerorder_id" in order_indexes:
op.drop_index("ix_orders_moysklad_customerorder_id", table_name="orders")
        order_columns = _column_names(inspector, "orders")
        if "moysklad_customerorder_id" in order_columns:
            op.drop_column("orders", "moysklad_customerorder_id")

    if _table_exists(inspector, "users"):
        user_indexes = _index_names(inspector, "users")
        if "ix_users_moysklad_counterparty_id" in user_indexes:
            op.drop_index("ix_users_moysklad_counterparty_id", table_name="users")
        user_columns = _column_names(inspector, "users")
        if "moysklad_counterparty_id" in user_columns:
            op.drop_column("users", "moysklad_counterparty_id")
