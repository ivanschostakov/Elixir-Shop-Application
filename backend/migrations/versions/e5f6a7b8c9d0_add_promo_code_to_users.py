"""add promo code to users

Revision ID: e5f6a7b8c9d0
Revises: 1d2e3f4a5b6c
Create Date: 2026-06-30 02:30:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "e5f6a7b8c9d0"
down_revision = "1d2e3f4a5b6c"
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
    if not _table_exists(inspector, "users"):
        return

    columns = _column_names(inspector, "users")
    if "promo_code" not in columns:
        op.add_column("users", sa.Column("promo_code", sa.String(length=120), nullable=True))

    inspector = sa.inspect(bind)
    indexes = _index_names(inspector, "users")
    if "ix_users_promo_code" not in indexes:
        op.create_index("ix_users_promo_code", "users", ["promo_code"], unique=False)

    if _table_exists(inspector, "referral_profiles"):
        op.execute(
            """
            UPDATE users
            SET promo_code = referral_profiles.referrer_promo_code
            FROM referral_profiles
            WHERE referral_profiles.user_id = users.id
              AND users.promo_code IS NULL
              AND referral_profiles.referrer_promo_code IS NOT NULL
            """
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not _table_exists(inspector, "users"):
        return

    indexes = _index_names(inspector, "users")
    if "ix_users_promo_code" in indexes:
        op.drop_index("ix_users_promo_code", table_name="users")

    columns = _column_names(inspector, "users")
    if "promo_code" in columns:
        op.drop_column("users", "promo_code")
