"""add telegram identity to users

Revision ID: 1d2e3f4a5b6c
Revises: f3c1d2e4b5a6
Create Date: 2026-06-29 14:30:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "1d2e3f4a5b6c"
down_revision = "f3c1d2e4b5a6"
branch_labels = None
depends_on = None


def _table_exists(inspector: sa.Inspector, table_name: str) -> bool:
    return table_name in inspector.get_table_names()


def _column_names(inspector: sa.Inspector, table_name: str) -> set[str]:
    return {column["name"] for column in inspector.get_columns(table_name)}


def _index_names(inspector: sa.Inspector, table_name: str) -> set[str | None]:
    return {index["name"] for index in inspector.get_indexes(table_name)}


def _unique_constraint_names(inspector: sa.Inspector, table_name: str) -> set[str | None]:
    return {constraint["name"] for constraint in inspector.get_unique_constraints(table_name)}


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not _table_exists(inspector, "users"):
        return

    columns = _column_names(inspector, "users")
    if "telegram_user_id" not in columns:
        op.add_column("users", sa.Column("telegram_user_id", sa.BigInteger(), nullable=True))
    if "telegram_username" not in columns:
        op.add_column("users", sa.Column("telegram_username", sa.String(length=64), nullable=True))
    if "telegram_phone_confirmed_at" not in columns:
        op.add_column("users", sa.Column("telegram_phone_confirmed_at", sa.DateTime(timezone=True), nullable=True))

    inspector = sa.inspect(bind)
    indexes = _index_names(inspector, "users")
    constraints = _unique_constraint_names(inspector, "users")
    if "ix_users_telegram_user_id" not in indexes:
        op.create_index("ix_users_telegram_user_id", "users", ["telegram_user_id"], unique=False)
    if "uq_users_telegram_user_id" not in constraints:
        op.create_unique_constraint("uq_users_telegram_user_id", "users", ["telegram_user_id"])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not _table_exists(inspector, "users"):
        return

    indexes = _index_names(inspector, "users")
    constraints = _unique_constraint_names(inspector, "users")
    columns = _column_names(inspector, "users")

    if "uq_users_telegram_user_id" in constraints:
        op.drop_constraint("uq_users_telegram_user_id", "users", type_="unique")
    if "ix_users_telegram_user_id" in indexes:
        op.drop_index("ix_users_telegram_user_id", table_name="users")
    if "telegram_phone_confirmed_at" in columns:
        op.drop_column("users", "telegram_phone_confirmed_at")
    if "telegram_username" in columns:
        op.drop_column("users", "telegram_username")
    if "telegram_user_id" in columns:
        op.drop_column("users", "telegram_user_id")
