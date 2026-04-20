"""add doses, baskets and basket items

Revision ID: c87f0fa65e1d
Revises: 6d0bb6c2ef8c
Create Date: 2026-04-04 20:30:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c87f0fa65e1d"
down_revision: Union[str, Sequence[str], None] = "6d0bb6c2ef8c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not inspector.has_table("doses"):
        op.create_table(
            "doses",
            sa.Column("product_id", sa.BigInteger(), nullable=False),
            sa.Column("sku", sa.String(length=64), nullable=True),
            sa.Column("name", sa.String(length=200), nullable=False),
            sa.Column("stock", sa.Integer(), nullable=False),
            sa.Column("price", sa.Numeric(12, 2), nullable=False),
            sa.Column("system_id", sa.UUID(), nullable=False),
            sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["product_id"], ["products.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("system_id"),
        )
        op.create_index(op.f("ix_doses_id"), "doses", ["id"], unique=False)
        op.create_index(op.f("ix_doses_product_id"), "doses", ["product_id"], unique=False)

    if not inspector.has_table("baskets"):
        op.create_table(
            "baskets",
            sa.Column("user_id", sa.BigInteger(), nullable=False),
            sa.Column("name", sa.String(length=200), nullable=False),
            sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(op.f("ix_baskets_id"), "baskets", ["id"], unique=False)
        op.create_index(op.f("ix_baskets_user_id"), "baskets", ["user_id"], unique=False)

    if not inspector.has_table("basket_items"):
        op.create_table(
            "basket_items",
            sa.Column("user_id", sa.BigInteger(), nullable=False),
            sa.Column("basket_id", sa.BigInteger(), nullable=False),
            sa.Column("product_id", sa.BigInteger(), nullable=False),
            sa.Column("dose_id", sa.BigInteger(), nullable=False),
            sa.Column("quantity", sa.Integer(), nullable=False),
            sa.Column("price", sa.Numeric(12, 2), nullable=False),
            sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.CheckConstraint("quantity >= 0", name="ck_basket_items_quantity_non_negative"),
            sa.ForeignKeyConstraint(["basket_id"], ["baskets.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["dose_id"], ["doses.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["product_id"], ["products.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(op.f("ix_basket_items_basket_id"), "basket_items", ["basket_id"], unique=False)
        op.create_index(op.f("ix_basket_items_dose_id"), "basket_items", ["dose_id"], unique=False)
        op.create_index(op.f("ix_basket_items_id"), "basket_items", ["id"], unique=False)
        op.create_index(op.f("ix_basket_items_product_id"), "basket_items", ["product_id"], unique=False)
        op.create_index(op.f("ix_basket_items_user_id"), "basket_items", ["user_id"], unique=False)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if inspector.has_table("basket_items"):
        op.drop_index(op.f("ix_basket_items_user_id"), table_name="basket_items")
        op.drop_index(op.f("ix_basket_items_product_id"), table_name="basket_items")
        op.drop_index(op.f("ix_basket_items_id"), table_name="basket_items")
        op.drop_index(op.f("ix_basket_items_dose_id"), table_name="basket_items")
        op.drop_index(op.f("ix_basket_items_basket_id"), table_name="basket_items")
        op.drop_table("basket_items")

    if inspector.has_table("baskets"):
        op.drop_index(op.f("ix_baskets_user_id"), table_name="baskets")
        op.drop_index(op.f("ix_baskets_id"), table_name="baskets")
        op.drop_table("baskets")

    if inspector.has_table("doses"):
        op.drop_index(op.f("ix_doses_product_id"), table_name="doses")
        op.drop_index(op.f("ix_doses_id"), table_name="doses")
        op.drop_table("doses")
