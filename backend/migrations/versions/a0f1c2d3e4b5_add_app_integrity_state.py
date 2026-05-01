"""add app integrity state

Revision ID: a0f1c2d3e4b5
Revises: 9f7c3a1b2d4e
Create Date: 2026-05-01 08:15:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a0f1c2d3e4b5"
down_revision: Union[str, Sequence[str], None] = "9f7c3a1b2d4e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "app_integrity_challenges",
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("challenge", sa.String(length=128), nullable=False),
        sa.Column("platform", sa.String(length=32), nullable=False),
        sa.Column("purpose", sa.String(length=32), nullable=False),
        sa.Column("action", sa.String(length=32), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_app_integrity_challenges_id"), "app_integrity_challenges", ["id"], unique=False)
    op.create_index(op.f("ix_app_integrity_challenges_user_id"), "app_integrity_challenges", ["user_id"], unique=False)
    op.create_index(op.f("ix_app_integrity_challenges_challenge"), "app_integrity_challenges", ["challenge"], unique=True)
    op.create_index(op.f("ix_app_integrity_challenges_platform"), "app_integrity_challenges", ["platform"], unique=False)
    op.create_index(op.f("ix_app_integrity_challenges_purpose"), "app_integrity_challenges", ["purpose"], unique=False)
    op.create_index(op.f("ix_app_integrity_challenges_action"), "app_integrity_challenges", ["action"], unique=False)
    op.create_index(op.f("ix_app_integrity_challenges_expires_at"), "app_integrity_challenges", ["expires_at"], unique=False)
    op.create_index(
        "ix_app_integrity_challenges_user_platform_purpose_action",
        "app_integrity_challenges",
        ["user_id", "platform", "purpose", "action"],
        unique=False,
    )

    op.create_table(
        "app_attest_keys",
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("key_id", sa.String(length=128), nullable=False),
        sa.Column("public_key_pem", sa.Text(), nullable=False),
        sa.Column("receipt_b64", sa.Text(), nullable=True),
        sa.Column("environment", sa.String(length=32), nullable=False),
        sa.Column("counter", sa.BigInteger(), server_default=sa.text("0"), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_app_attest_keys_id"), "app_attest_keys", ["id"], unique=False)
    op.create_index(op.f("ix_app_attest_keys_user_id"), "app_attest_keys", ["user_id"], unique=False)
    op.create_index(op.f("ix_app_attest_keys_key_id"), "app_attest_keys", ["key_id"], unique=True)
    op.create_index(
        "ix_app_attest_keys_user_active",
        "app_attest_keys",
        ["user_id", "is_active"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_app_attest_keys_user_active", table_name="app_attest_keys")
    op.drop_index(op.f("ix_app_attest_keys_key_id"), table_name="app_attest_keys")
    op.drop_index(op.f("ix_app_attest_keys_user_id"), table_name="app_attest_keys")
    op.drop_index(op.f("ix_app_attest_keys_id"), table_name="app_attest_keys")
    op.drop_table("app_attest_keys")

    op.drop_index("ix_app_integrity_challenges_user_platform_purpose_action", table_name="app_integrity_challenges")
    op.drop_index(op.f("ix_app_integrity_challenges_expires_at"), table_name="app_integrity_challenges")
    op.drop_index(op.f("ix_app_integrity_challenges_action"), table_name="app_integrity_challenges")
    op.drop_index(op.f("ix_app_integrity_challenges_purpose"), table_name="app_integrity_challenges")
    op.drop_index(op.f("ix_app_integrity_challenges_platform"), table_name="app_integrity_challenges")
    op.drop_index(op.f("ix_app_integrity_challenges_challenge"), table_name="app_integrity_challenges")
    op.drop_index(op.f("ix_app_integrity_challenges_user_id"), table_name="app_integrity_challenges")
    op.drop_index(op.f("ix_app_integrity_challenges_id"), table_name="app_integrity_challenges")
    op.drop_table("app_integrity_challenges")
