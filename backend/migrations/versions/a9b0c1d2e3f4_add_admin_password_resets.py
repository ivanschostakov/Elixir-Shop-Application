"""add one-time admin password reset tokens

Revision ID: a9b0c1d2e3f4
Revises: f8a9b0c1d2e3
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "a9b0c1d2e3f4"
down_revision: str | Sequence[str] | None = "f8a9b0c1d2e3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "admin_password_resets",
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("requested_ip", sa.String(length=64), nullable=True),
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["admins.user_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_admin_password_resets_id"), "admin_password_resets", ["id"])
    op.create_index(op.f("ix_admin_password_resets_user_id"), "admin_password_resets", ["user_id"])
    op.create_index(op.f("ix_admin_password_resets_token_hash"), "admin_password_resets", ["token_hash"], unique=True)
    op.create_index(op.f("ix_admin_password_resets_expires_at"), "admin_password_resets", ["expires_at"])
    op.create_index(
        "ix_admin_password_resets_user_active",
        "admin_password_resets",
        ["user_id", "used_at", "expires_at"],
    )


def downgrade() -> None:
    op.drop_table("admin_password_resets")
