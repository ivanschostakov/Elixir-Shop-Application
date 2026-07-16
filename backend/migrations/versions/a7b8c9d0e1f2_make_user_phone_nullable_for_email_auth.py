"""make user phone nullable for email auth

Revision ID: a7b8c9d0e1f2
Revises: f6a7b8c9d0e1
Create Date: 2026-07-16 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "a7b8c9d0e1f2"
down_revision = "f6a7b8c9d0e1"
branch_labels = None
depends_on = None


def _table_exists(table_name: str) -> bool:
    return sa.inspect(op.get_bind()).has_table(table_name)


def _column_names(table_name: str) -> set[str]:
    if not _table_exists(table_name):
        return set()
    return {column["name"] for column in sa.inspect(op.get_bind()).get_columns(table_name)}


def upgrade() -> None:
    if "phone_number" in _column_names("users"):
        op.alter_column("users", "phone_number", existing_type=sa.String(length=20), nullable=True)


def downgrade() -> None:
    if "phone_number" not in _column_names("users"):
        return
    op.execute(
        sa.text(
            """
            update users
            set phone_number = '+97' || right(lpad(id::text, 13, '0'), 13)
            where phone_number is null
            """
        )
    )
    op.alter_column("users", "phone_number", existing_type=sa.String(length=20), nullable=False)
