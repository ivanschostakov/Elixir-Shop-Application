"""add product is_active stock watcher

Revision ID: 7d7f1f1f2e2b
Revises: d7a65071491d
Create Date: 2026-04-08 10:30:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "7d7f1f1f2e2b"
down_revision: Union[str, Sequence[str], None] = "d7a65071491d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


PRODUCTS_TABLE = "products"
DOSES_TABLE = "doses"
IS_ACTIVE_COLUMN = "is_active"
REFRESH_FUNCTION_NAME = "refresh_product_is_active"
TRIGGER_FUNCTION_NAME = "sync_product_is_active_from_doses"
TRIGGER_NAME = "trg_sync_product_is_active_from_doses"


def _column_names(inspector: sa.Inspector, table_name: str) -> set[str]:
    return {column["name"] for column in inspector.get_columns(table_name)}


def _create_functions() -> None:
    op.execute(
        f"""
        CREATE OR REPLACE FUNCTION {REFRESH_FUNCTION_NAME}(target_product_id BIGINT)
        RETURNS VOID
        LANGUAGE plpgsql
        AS $$
        BEGIN
            IF target_product_id IS NULL THEN
                RETURN;
            END IF;

            UPDATE {PRODUCTS_TABLE} p
            SET {IS_ACTIVE_COLUMN} = COALESCE(
                (
                    SELECT SUM(d.stock) > 0
                    FROM {DOSES_TABLE} d
                    WHERE d.product_id = target_product_id
                ),
                FALSE
            )
            WHERE p.id = target_product_id;
        END;
        $$;
        """
    )
    op.execute(
        f"""
        CREATE OR REPLACE FUNCTION {TRIGGER_FUNCTION_NAME}()
        RETURNS TRIGGER
        LANGUAGE plpgsql
        AS $$
        BEGIN
            IF TG_OP <> 'INSERT' THEN
                PERFORM {REFRESH_FUNCTION_NAME}(OLD.product_id);
            END IF;

            IF TG_OP <> 'DELETE' THEN
                PERFORM {REFRESH_FUNCTION_NAME}(NEW.product_id);
            END IF;

            RETURN NULL;
        END;
        $$;
        """
    )


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not inspector.has_table(PRODUCTS_TABLE):
        return

    columns = _column_names(inspector, PRODUCTS_TABLE)
    if IS_ACTIVE_COLUMN not in columns:
        op.add_column(PRODUCTS_TABLE, sa.Column(IS_ACTIVE_COLUMN, sa.Boolean(), nullable=False, server_default=sa.text("false")))

    _create_functions()

    if inspector.has_table(DOSES_TABLE):
        op.execute(f"DROP TRIGGER IF EXISTS {TRIGGER_NAME} ON {DOSES_TABLE}")
        op.execute(
            f"""
            CREATE TRIGGER {TRIGGER_NAME}
            AFTER INSERT OR UPDATE OR DELETE
            ON {DOSES_TABLE}
            FOR EACH ROW
            EXECUTE FUNCTION {TRIGGER_FUNCTION_NAME}();
            """
        )
        op.execute(
            f"""
            UPDATE {PRODUCTS_TABLE} p
            SET {IS_ACTIVE_COLUMN} = COALESCE(
                (
                    SELECT SUM(d.stock) > 0
                    FROM {DOSES_TABLE} d
                    WHERE d.product_id = p.id
                ),
                FALSE
            );
            """
        )
    else:
        op.execute(f"UPDATE {PRODUCTS_TABLE} SET {IS_ACTIVE_COLUMN} = FALSE")

    op.alter_column(PRODUCTS_TABLE, IS_ACTIVE_COLUMN, server_default=None)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if inspector.has_table(DOSES_TABLE):
        op.execute(f"DROP TRIGGER IF EXISTS {TRIGGER_NAME} ON {DOSES_TABLE}")

    op.execute(f"DROP FUNCTION IF EXISTS {TRIGGER_FUNCTION_NAME}()")
    op.execute(f"DROP FUNCTION IF EXISTS {REFRESH_FUNCTION_NAME}(BIGINT)")

    if inspector.has_table(PRODUCTS_TABLE):
        columns = _column_names(inspector, PRODUCTS_TABLE)
        if IS_ACTIVE_COLUMN in columns:
            op.drop_column(PRODUCTS_TABLE, IS_ACTIVE_COLUMN)
