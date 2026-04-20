"""add favoured products table

Revision ID: 5864e4fb2c57
Revises: 2fac1df2cc97
Create Date: 2026-03-23 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "5864e4fb2c57"
down_revision: Union[str, Sequence[str], None] = "2fac1df2cc97"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "favoured_products",
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("product_id", sa.BigInteger(), nullable=False),
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_favoured_products_id"), "favoured_products", ["id"], unique=False)
    op.create_index(op.f("ix_favoured_products_product_id"), "favoured_products", ["product_id"], unique=False)
    op.create_index(op.f("ix_favoured_products_user_id"), "favoured_products", ["user_id"], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f("ix_favoured_products_user_id"), table_name="favoured_products")
    op.drop_index(op.f("ix_favoured_products_product_id"), table_name="favoured_products")
    op.drop_index(op.f("ix_favoured_products_id"), table_name="favoured_products")
    op.drop_table("favoured_products")
