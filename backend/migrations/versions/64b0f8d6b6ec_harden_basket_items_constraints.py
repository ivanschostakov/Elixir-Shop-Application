"""harden basket items constraints

Revision ID: 64b0f8d6b6ec
Revises: 8b3a859f5ff7
Create Date: 2026-04-08 12:10:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "64b0f8d6b6ec"
down_revision: Union[str, Sequence[str], None] = "8b3a859f5ff7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


TABLE_NAME = "basket_items"
DOSES_TABLE = "doses"
OLD_CHECK_NAME = "ck_basket_items_quantity_non_negative"
NEW_CHECK_NAME = "ck_basket_items_quantity_positive"
UNIQUE_CONSTRAINT_NAME = "uq_basket_items_basket_id_dose_id"


def _check_constraint_names(inspector: sa.Inspector, table_name: str) -> set[str]:
    return {constraint["name"] for constraint in inspector.get_check_constraints(table_name) if constraint.get("name")}


def _has_unique_basket_variant_constraint(inspector: sa.Inspector) -> bool:
    for constraint in inspector.get_unique_constraints(TABLE_NAME):
        if tuple(constraint.get("column_names") or ()) == ("basket_id", "dose_id"):
            return True

    for index in inspector.get_indexes(TABLE_NAME):
        if index.get("unique") and tuple(index.get("column_names") or ()) == ("basket_id", "dose_id"):
            return True

    return False


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not inspector.has_table(TABLE_NAME):
        return

    bind.execute(sa.text(f"DELETE FROM {TABLE_NAME} WHERE quantity <= 0"))

    if inspector.has_table(DOSES_TABLE):
        bind.execute(
            sa.text(
                f"""
                UPDATE {TABLE_NAME} AS basket_items
                SET product_id = doses.product_id,
                    price = doses.price,
                    updated_at = CURRENT_TIMESTAMP
                FROM {DOSES_TABLE} AS doses
                WHERE doses.id = basket_items.dose_id
                  AND (
                    basket_items.product_id IS DISTINCT FROM doses.product_id
                    OR basket_items.price IS DISTINCT FROM doses.price
                  )
                """
            )
        )

    bind.execute(
        sa.text(
            f"""
            WITH duplicates AS (
                SELECT MIN(id) AS keep_id, basket_id, dose_id, SUM(quantity) AS total_quantity
                FROM {TABLE_NAME}
                GROUP BY basket_id, dose_id
                HAVING COUNT(*) > 1
            )
            UPDATE {TABLE_NAME} AS basket_items
            SET quantity = duplicates.total_quantity,
                updated_at = CURRENT_TIMESTAMP
            FROM duplicates
            WHERE basket_items.id = duplicates.keep_id
            """
        )
    )
    bind.execute(
        sa.text(
            f"""
            WITH duplicates AS (
                SELECT MIN(id) AS keep_id, basket_id, dose_id
                FROM {TABLE_NAME}
                GROUP BY basket_id, dose_id
                HAVING COUNT(*) > 1
            )
            DELETE FROM {TABLE_NAME} AS basket_items
            USING duplicates
            WHERE basket_items.basket_id = duplicates.basket_id
              AND basket_items.dose_id = duplicates.dose_id
              AND basket_items.id <> duplicates.keep_id
            """
        )
    )

    inspector = sa.inspect(bind)
    check_names = _check_constraint_names(inspector, TABLE_NAME)
    if OLD_CHECK_NAME in check_names:
        op.drop_constraint(OLD_CHECK_NAME, TABLE_NAME, type_="check")
        check_names.remove(OLD_CHECK_NAME)
    if NEW_CHECK_NAME not in check_names:
        op.create_check_constraint(NEW_CHECK_NAME, TABLE_NAME, "quantity > 0")

    if not _has_unique_basket_variant_constraint(sa.inspect(bind)):
        op.create_unique_constraint(UNIQUE_CONSTRAINT_NAME, TABLE_NAME, ["basket_id", "dose_id"])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not inspector.has_table(TABLE_NAME):
        return

    unique_constraints = {constraint["name"] for constraint in inspector.get_unique_constraints(TABLE_NAME) if constraint.get("name")}
    if UNIQUE_CONSTRAINT_NAME in unique_constraints:
        op.drop_constraint(UNIQUE_CONSTRAINT_NAME, TABLE_NAME, type_="unique")

    check_names = _check_constraint_names(sa.inspect(bind), TABLE_NAME)
    if NEW_CHECK_NAME in check_names:
        op.drop_constraint(NEW_CHECK_NAME, TABLE_NAME, type_="check")
        check_names.remove(NEW_CHECK_NAME)
    if OLD_CHECK_NAME not in check_names:
        op.create_check_constraint(OLD_CHECK_NAME, TABLE_NAME, "quantity >= 0")
