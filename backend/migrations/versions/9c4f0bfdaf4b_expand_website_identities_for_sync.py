"""expand website website_identity for sync

Revision ID: 9c4f0bfdaf4b
Revises: 5864e4fb2c57
Create Date: 2026-03-23 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "9c4f0bfdaf4b"
down_revision: Union[str, Sequence[str], None] = "5864e4fb2c57"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


TABLE_NAME = "website_identities"


def _expansion_columns() -> list[sa.Column]:
    return [
        sa.Column("website_login", sa.String(length=120), nullable=False, server_default=""),
        sa.Column("website_email", sa.String(length=190), nullable=True),
        sa.Column("website_name", sa.String(length=120), nullable=True),
        sa.Column("website_last_name", sa.String(length=120), nullable=True),
        sa.Column("website_second_name", sa.String(length=120), nullable=True),
        sa.Column("website_phone", sa.String(length=80), nullable=True),
        sa.Column("website_mobile", sa.String(length=80), nullable=True),
        sa.Column("website_city", sa.String(length=120), nullable=True),
        sa.Column("website_registered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("website_last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("group_ids", sa.JSON(), nullable=False, server_default=sa.text("'[]'::json")),
        sa.Column("group_names", sa.JSON(), nullable=False, server_default=sa.text("'[]'::json")),
        sa.Column("custom_fields", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column("referral_program", sa.JSON(), nullable=True),
        sa.Column("bonus_account", sa.JSON(), nullable=True),
        sa.Column("discount_groups", sa.JSON(), nullable=False, server_default=sa.text("'[]'::json")),
        sa.Column("active_coupons", sa.JSON(), nullable=False, server_default=sa.text("'[]'::json")),
        sa.Column("recent_used_coupons", sa.JSON(), nullable=False, server_default=sa.text("'[]'::json")),
        sa.Column("raw_payload", sa.JSON(), nullable=True),
        sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=True),
    ]


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not inspector.has_table(TABLE_NAME):
        op.create_table(
            TABLE_NAME,
            sa.Column("user_id", sa.BigInteger(), nullable=False),
            sa.Column("website_user_id", sa.BigInteger(), nullable=False),
            *_expansion_columns(),
            sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(op.f("ix_website_identities_id"), TABLE_NAME, ["id"], unique=False)
        op.create_index(op.f("ix_website_identities_user_id"), TABLE_NAME, ["user_id"], unique=True)
        op.create_index(op.f("ix_website_identities_website_user_id"), TABLE_NAME, ["website_user_id"], unique=True)
        return

    existing_columns = {column["name"] for column in inspector.get_columns(TABLE_NAME)}
    for column in _expansion_columns():
        if column.name not in existing_columns:
            op.add_column(TABLE_NAME, column)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table(TABLE_NAME):
        return

    existing_columns = {column["name"] for column in inspector.get_columns(TABLE_NAME)}
    for column_name in reversed([column.name for column in _expansion_columns()]):
        if column_name in existing_columns:
            op.drop_column(TABLE_NAME, column_name)
