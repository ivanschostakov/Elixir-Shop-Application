"""rename product stock marker to in_stock

Revision ID: 3a5e62ea7c88
Revises: 7d7f1f1f2e2b
Create Date: 2026-04-08 10:50:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "3a5e62ea7c88"
down_revision: Union[str, Sequence[str], None] = "7d7f1f1f2e2b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


PRODUCTS_TABLE = "products"
DOSES_TABLE = "doses"
OLD_COLUMN_NAME = "is_active"
NEW_COLUMN_NAME = "in_stock"
OLD_REFRESH_FUNCTION_NAME = "refresh_product_is_active"
NEW_REFRESH_FUNCTION_NAME = "refresh_product_in_stock"
OLD_TRIGGER_FUNCTION_NAME = "sync_product_is_active_from_doses"
NEW_TRIGGER_FUNCTION_NAME = "sync_product_in_stock_from_doses"
OLD_TRIGGER_NAME = "trg_sync_product_is_active_from_doses"
NEW_TRIGGER_NAME = "trg_sync_product_in_stock_from_doses"


def _column_names(inspector: sa.Inspector, table_name: str) -> set[str]:
    return {column["name"] for column in inspector.get_columns(table_name)}


def _drop_stock_watcher() -> None:
    op.execute(f"DROP TRIGGER IF EXISTS {OLD_TRIGGER_NAME} ON {DOSES_TABLE}")
    op.execute(f"DROP TRIGGER IF EXISTS {NEW_TRIGGER_NAME} ON {DOSES_TABLE}")
    op.execute(f"DROP FUNCTION IF EXISTS {OLD_TRIGGER_FUNCTION_NAME}()")
    op.execute(f"DROP FUNCTION IF EXISTS {NEW_TRIGGER_FUNCTION_NAME}()")
    op.execute(f"DROP FUNCTION IF EXISTS {OLD_REFRESH_FUNCTION_NAME}(BIGINT)")
    op.execute(f"DROP FUNCTION IF EXISTS {NEW_REFRESH_FUNCTION_NAME}(BIGINT)")


def _create_stock_watcher(column_name: str, refresh_function_name: str, trigger_function_name: str, trigger_name: str) -> None:
    op.execute(
        f"""
        CREATE OR REPLACE FUNCTION {refresh_function_name}(target_product_id BIGINT)
        RETURNS VOID
        LANGUAGE plpgsql
        AS $$
        BEGIN
            IF target_product_id IS NULL THEN
                RETURN;
            END IF;

            UPDATE {PRODUCTS_TABLE} p
            SET {column_name} = COALESCE(
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
        CREATE OR REPLACE FUNCTION {trigger_function_name}()
        RETURNS TRIGGER
        LANGUAGE plpgsql
        AS $$
        BEGIN
            IF TG_OP <> 'INSERT' THEN
                PERFORM {refresh_function_name}(OLD.product_id);
            END IF;

            IF TG_OP <> 'DELETE' THEN
                PERFORM {refresh_function_name}(NEW.product_id);
            END IF;

            RETURN NULL;
        END;
        $$;
        """
    )
    op.execute(
        f"""
        CREATE TRIGGER {trigger_name}
        AFTER INSERT OR UPDATE OR DELETE
        ON {DOSES_TABLE}
        FOR EACH ROW
        EXECUTE FUNCTION {trigger_function_name}();
        """
    )


def _refresh_stock_column(column_name: str) -> None:
    op.execute(
        f"""
        UPDATE {PRODUCTS_TABLE} p
        SET {column_name} = COALESCE(
            (
                SELECT SUM(d.stock) > 0
                FROM {DOSES_TABLE} d
                WHERE d.product_id = p.id
            ),
            FALSE
        );
        """
    )


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not inspector.has_table(PRODUCTS_TABLE):
        return

    columns = _column_names(inspector, PRODUCTS_TABLE)
    if OLD_COLUMN_NAME in columns and NEW_COLUMN_NAME not in columns:
        op.alter_column(PRODUCTS_TABLE, OLD_COLUMN_NAME, new_column_name=NEW_COLUMN_NAME)
    elif NEW_COLUMN_NAME not in columns:
        op.add_column(PRODUCTS_TABLE, sa.Column(NEW_COLUMN_NAME, sa.Boolean(), nullable=False, server_default=sa.text("false")))

    if inspector.has_table(DOSES_TABLE):
        _drop_stock_watcher()
        _create_stock_watcher(
            column_name=NEW_COLUMN_NAME,
            refresh_function_name=NEW_REFRESH_FUNCTION_NAME,
            trigger_function_name=NEW_TRIGGER_FUNCTION_NAME,
            trigger_name=NEW_TRIGGER_NAME,
        )
        _refresh_stock_column(NEW_COLUMN_NAME)
    else:
        op.execute(f"UPDATE {PRODUCTS_TABLE} SET {NEW_COLUMN_NAME} = FALSE")

    op.alter_column(PRODUCTS_TABLE, NEW_COLUMN_NAME, server_default=None)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not inspector.has_table(PRODUCTS_TABLE):
        return

    columns = _column_names(inspector, PRODUCTS_TABLE)

    if inspector.has_table(DOSES_TABLE):
        _drop_stock_watcher()

    if NEW_COLUMN_NAME in columns and OLD_COLUMN_NAME not in columns:
        op.alter_column(PRODUCTS_TABLE, NEW_COLUMN_NAME, new_column_name=OLD_COLUMN_NAME)
        target_column_name = OLD_COLUMN_NAME
    else:
        target_column_name = OLD_COLUMN_NAME if OLD_COLUMN_NAME in columns else NEW_COLUMN_NAME

    if inspector.has_table(DOSES_TABLE) and target_column_name in _column_names(sa.inspect(bind), PRODUCTS_TABLE):
        _create_stock_watcher(
            column_name=target_column_name,
            refresh_function_name=OLD_REFRESH_FUNCTION_NAME,
            trigger_function_name=OLD_TRIGGER_FUNCTION_NAME,
            trigger_name=OLD_TRIGGER_NAME,
        )
        _refresh_stock_column(target_column_name)
