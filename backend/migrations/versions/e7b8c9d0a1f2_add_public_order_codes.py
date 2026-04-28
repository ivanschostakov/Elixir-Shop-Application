"""add public order codes

Revision ID: e7b8c9d0a1f2
Revises: b4d2f7a9c8e1
Create Date: 2026-04-28 02:20:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "e7b8c9d0a1f2"
down_revision: Union[str, Sequence[str], None] = "b4d2f7a9c8e1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("orders", sa.Column("order_code", sa.String(length=24), nullable=True))
    op.execute(
        sa.text(
            """
            UPDATE orders
            SET order_code = 'EP-' || upper(substr(md5(id::text || '-' || created_at::text), 1, 8))
            WHERE order_code IS NULL
            """
        )
    )
    op.alter_column("orders", "order_code", existing_type=sa.String(length=24), nullable=False)
    op.create_index(op.f("ix_orders_order_code"), "orders", ["order_code"], unique=True)


def downgrade() -> None:
    op.drop_index(op.f("ix_orders_order_code"), table_name="orders")
    op.drop_column("orders", "order_code")
