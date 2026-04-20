"""add product categories and links

Revision ID: 3f5fbc8890f8
Revises: 9c4f0bfdaf4b
Create Date: 2026-04-01 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "3f5fbc8890f8"
down_revision: Union[str, Sequence[str], None] = "9c4f0bfdaf4b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "product_categories",
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("description", sa.String(length=5000), nullable=True),
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )
    op.create_index(op.f("ix_product_categories_id"), "product_categories", ["id"], unique=False)

    op.create_table(
        "products_by_category",
        sa.Column("product_id", sa.BigInteger(), nullable=False),
        sa.Column("category_id", sa.BigInteger(), nullable=False),
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["category_id"], ["product_categories.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("product_id", "category_id", name="uq_products_by_category_product_id_category_id"),
    )
    op.create_index(op.f("ix_products_by_category_category_id"), "products_by_category", ["category_id"], unique=False)
    op.create_index(op.f("ix_products_by_category_id"), "products_by_category", ["id"], unique=False)
    op.create_index(op.f("ix_products_by_category_product_id"), "products_by_category", ["product_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_products_by_category_product_id"), table_name="products_by_category")
    op.drop_index(op.f("ix_products_by_category_id"), table_name="products_by_category")
    op.drop_index(op.f("ix_products_by_category_category_id"), table_name="products_by_category")
    op.drop_table("products_by_category")

    op.drop_index(op.f("ix_product_categories_id"), table_name="product_categories")
    op.drop_table("product_categories")
