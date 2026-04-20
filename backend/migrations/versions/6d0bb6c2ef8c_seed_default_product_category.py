"""seed default product category

Revision ID: 6d0bb6c2ef8c
Revises: 3f5fbc8890f8
Create Date: 2026-04-01 00:30:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "6d0bb6c2ef8c"
down_revision: Union[str, Sequence[str], None] = "3f5fbc8890f8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


DEFAULT_CATEGORY_NAME = "Пептиды"


def _table_exists(inspector: sa.Inspector, table_name: str) -> bool:
    return inspector.has_table(table_name)


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not all(_table_exists(inspector, table_name) for table_name in ("products", "product_categories", "products_by_category")):
        return

    category_id = bind.execute(
        sa.text("select id from product_categories where name = :name limit 1"), {"name": DEFAULT_CATEGORY_NAME}
    ).scalar_one_or_none()

    if category_id is None:
        category_count = bind.execute(sa.text("select count(*) from product_categories")).scalar_one()
        if category_count == 0:
            category_id = bind.execute(
                sa.text(
                    """
                    insert into product_categories (name, description, created_at, updated_at)
                    values (:name, null, current_timestamp, current_timestamp)
                    returning id
                    """
                ),
                {"name": DEFAULT_CATEGORY_NAME},
            ).scalar_one()

    link_count = bind.execute(sa.text("select count(*) from products_by_category")).scalar_one()
    if link_count == 0 and category_id is not None:
        bind.execute(
            sa.text(
                """
                insert into products_by_category (product_id, category_id, created_at, updated_at)
                select p.id, :category_id, current_timestamp, current_timestamp
                from products p
                """
            ),
            {"category_id": category_id},
        )


def downgrade() -> None:
    # This is a one-time seed/backfill migration; downgrading should keep data intact.
    return
