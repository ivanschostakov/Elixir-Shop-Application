"""fix product stock trigger to use variants

Revision ID: d8e9f0a1b2c3
Revises: c7d8e9f0a1b2
Create Date: 2026-05-04 15:45:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "d8e9f0a1b2c3"
down_revision: Union[str, Sequence[str], None] = "c7d8e9f0a1b2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


PRODUCTS_TABLE = "products"
VARIANTS_TABLE = "variants"
DOSES_TABLE = "doses"
REFRESH_FUNCTION_NAME = "refresh_product_in_stock"
OLD_TRIGGER_FUNCTION_NAME = "sync_product_in_stock_from_doses"
TRIGGER_FUNCTION_NAME = "sync_product_in_stock_from_variants"
OLD_TRIGGER_NAME = "trg_sync_product_in_stock_from_doses"
TRIGGER_NAME = "trg_sync_product_in_stock_from_variants"


def _column_names(inspector: sa.Inspector, table_name: str) -> set[str]:
    return {column["name"] for column in inspector.get_columns(table_name)}


def _drop_stock_watcher() -> None:
    op.execute(f"DROP TRIGGER IF EXISTS {OLD_TRIGGER_NAME} ON {DOSES_TABLE}")
    op.execute(f"DROP TRIGGER IF EXISTS {OLD_TRIGGER_NAME} ON {VARIANTS_TABLE}")
    op.execute(f"DROP TRIGGER IF EXISTS {TRIGGER_NAME} ON {VARIANTS_TABLE}")
    op.execute(f"DROP FUNCTION IF EXISTS {OLD_TRIGGER_FUNCTION_NAME}()")
    op.execute(f"DROP FUNCTION IF EXISTS {TRIGGER_FUNCTION_NAME}()")
    op.execute(f"DROP FUNCTION IF EXISTS {REFRESH_FUNCTION_NAME}(BIGINT)")


def _create_variant_stock_watcher() -> None:
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
            SET in_stock = COALESCE(
                (
                    SELECT SUM(v.stock) > 0
                    FROM {VARIANTS_TABLE} v
                    WHERE v.product_id = target_product_id
                      AND COALESCE(v.archived, FALSE) = FALSE
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
    op.execute(
        f"""
        CREATE TRIGGER {TRIGGER_NAME}
        AFTER INSERT OR UPDATE OR DELETE
        ON {VARIANTS_TABLE}
        FOR EACH ROW
        EXECUTE FUNCTION {TRIGGER_FUNCTION_NAME}();
        """
    )


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table(PRODUCTS_TABLE) or not inspector.has_table(VARIANTS_TABLE):
        return

    product_columns = _column_names(inspector, PRODUCTS_TABLE)
    variant_columns = _column_names(inspector, VARIANTS_TABLE)
    if "in_stock" not in product_columns or "stock" not in variant_columns:
        return

    if "archived" not in variant_columns:
        op.add_column(
            VARIANTS_TABLE,
            sa.Column("archived", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        )

    _drop_stock_watcher()
    _create_variant_stock_watcher()
    op.execute(
        f"""
        UPDATE {PRODUCTS_TABLE} p
        SET in_stock = COALESCE(
            (
                SELECT SUM(v.stock) > 0
                FROM {VARIANTS_TABLE} v
                WHERE v.product_id = p.id
                  AND COALESCE(v.archived, FALSE) = FALSE
            ),
            FALSE
        );
        """
    )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table(PRODUCTS_TABLE) or not inspector.has_table(VARIANTS_TABLE):
        return

    _drop_stock_watcher()
