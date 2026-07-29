"""add product questions and review anonymity

Revision ID: a1c2e3f4b5d6
Revises: d9e0f1a2b3c4
Create Date: 2026-07-30 03:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "a1c2e3f4b5d6"
down_revision: str | Sequence[str] | None = "d9e0f1a2b3c4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "reviews",
        sa.Column(
            "hide_sender_name",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.create_table(
        "product_questions",
        sa.Column("user_id", sa.BigInteger(), nullable=True),
        sa.Column("product_id", sa.BigInteger(), nullable=False),
        sa.Column("guest_name", sa.String(length=120), nullable=True),
        sa.Column("text", sa.String(length=2000), nullable=False),
        sa.Column("answer", sa.String(length=4000), nullable=True),
        sa.Column("internal_moderation_comment", sa.String(length=4000), nullable=True),
        sa.Column("moderated", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("moderated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("moderated_by_user_id", sa.BigInteger(), nullable=True),
        sa.Column("rejected_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["moderated_by_user_id"], ["admins.user_id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_product_questions_id"), "product_questions", ["id"])
    op.create_index(op.f("ix_product_questions_product_id"), "product_questions", ["product_id"])
    op.create_index(op.f("ix_product_questions_user_id"), "product_questions", ["user_id"])
    op.create_index(
        op.f("ix_product_questions_moderated_by_user_id"),
        "product_questions",
        ["moderated_by_user_id"],
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_product_questions_moderated_by_user_id"),
        table_name="product_questions",
    )
    op.drop_index(op.f("ix_product_questions_user_id"), table_name="product_questions")
    op.drop_index(op.f("ix_product_questions_product_id"), table_name="product_questions")
    op.drop_index(op.f("ix_product_questions_id"), table_name="product_questions")
    op.drop_table("product_questions")
    op.drop_column("reviews", "hide_sender_name")
