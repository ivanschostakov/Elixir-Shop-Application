"""add email verification codes

Revision ID: b4d2f7a9c8e1
Revises: a9f4c2d7e1b8
Create Date: 2026-04-28 00:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "b4d2f7a9c8e1"
down_revision: Union[str, Sequence[str], None] = "a9f4c2d7e1b8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "email_verification_codes",
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("code_hash", sa.String(length=255), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_email_verification_codes_id"), "email_verification_codes", ["id"], unique=False)
    op.create_index(op.f("ix_email_verification_codes_user_id"), "email_verification_codes", ["user_id"], unique=False)
    op.create_index(op.f("ix_email_verification_codes_expires_at"), "email_verification_codes", ["expires_at"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_email_verification_codes_expires_at"), table_name="email_verification_codes")
    op.drop_index(op.f("ix_email_verification_codes_user_id"), table_name="email_verification_codes")
    op.drop_index(op.f("ix_email_verification_codes_id"), table_name="email_verification_codes")
    op.drop_table("email_verification_codes")
