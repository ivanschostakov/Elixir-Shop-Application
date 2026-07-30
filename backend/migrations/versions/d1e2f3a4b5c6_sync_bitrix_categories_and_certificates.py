"""sync Bitrix categories and product certificates

Revision ID: d1e2f3a4b5c6
Revises: d0e1f2a3b4c5
Create Date: 2026-07-30 18:30:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "d1e2f3a4b5c6"
down_revision: str | Sequence[str] | None = "d0e1f2a3b4c5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "product_categories",
        sa.Column("website_category_id", sa.BigInteger(), nullable=True),
    )
    op.create_index(
        "ix_product_categories_website_category_id",
        "product_categories",
        ["website_category_id"],
        unique=True,
    )
    op.create_table(
        "product_certificates",
        sa.Column("product_id", sa.BigInteger(), nullable=False),
        sa.Column("website_file_id", sa.BigInteger(), nullable=False),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("original_name", sa.String(length=500), nullable=True),
        sa.Column("content_type", sa.String(length=255), nullable=True),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("url", sa.String(length=2048), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["product_id"],
            ["products.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "product_id",
            "website_file_id",
            name="uq_product_certificates_product_id_website_file_id",
        ),
    )
    op.create_index(
        "ix_product_certificates_product_id",
        "product_certificates",
        ["product_id"],
        unique=False,
    )
    op.create_index(
        "ix_product_certificates_id",
        "product_certificates",
        ["id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_product_certificates_id",
        table_name="product_certificates",
    )
    op.drop_index(
        "ix_product_certificates_product_id",
        table_name="product_certificates",
    )
    op.drop_table("product_certificates")
    op.drop_index(
        "ix_product_categories_website_category_id",
        table_name="product_categories",
    )
    op.drop_column("product_categories", "website_category_id")
