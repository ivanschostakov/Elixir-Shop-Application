"""unarchive catalog and ensure banner archived default

Revision ID: b3f4e2a1c7d9
Revises: a4b6c8d0e2f1
Create Date: 2026-05-11 18:25:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "b3f4e2a1c7d9"
down_revision = "a4b6c8d0e2f1"
branch_labels = None
depends_on = None


def _table_exists(inspector: sa.Inspector, table_name: str) -> bool:
    return table_name in inspector.get_table_names()


def _column_names(inspector: sa.Inspector, table_name: str) -> set[str]:
    return {column["name"] for column in inspector.get_columns(table_name)}


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if _table_exists(inspector, "banners"):
        banner_columns = _column_names(inspector, "banners")
        if "archived" not in banner_columns:
            op.add_column(
                "banners",
                sa.Column("archived", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            )
            banner_columns = _column_names(sa.inspect(bind), "banners")
        else:
            op.execute(sa.text("UPDATE banners SET archived = false WHERE archived IS NULL"))
            op.alter_column(
                "banners",
                "archived",
                existing_type=sa.Boolean(),
                nullable=False,
                server_default=sa.text("false"),
            )

    for table_name in ("product_categories", "products", "variants", "banners"):
        if not _table_exists(inspector, table_name):
            continue

        columns = _column_names(inspector, table_name)
        if "archived" not in columns:
            continue

        if "updated_at" in columns:
            op.execute(
                sa.text(
                    f"UPDATE {table_name} SET archived = false, updated_at = now() "
                    "WHERE archived IS DISTINCT FROM false"
                )
            )
        else:
            op.execute(sa.text(f"UPDATE {table_name} SET archived = false WHERE archived IS DISTINCT FROM false"))


def downgrade() -> None:
    pass
