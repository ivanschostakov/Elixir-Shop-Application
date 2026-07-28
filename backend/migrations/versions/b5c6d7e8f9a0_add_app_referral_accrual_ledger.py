"""add app referral accrual ledger

Revision ID: b5c6d7e8f9a0
Revises: e3f4a5b6c7d8
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "b5c6d7e8f9a0"
down_revision: str | Sequence[str] | None = "e3f4a5b6c7d8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "app_referral_purchases",
        sa.Column("order_id", sa.BigInteger(), nullable=False),
        sa.Column("buyer_user_id", sa.BigInteger(), nullable=True),
        sa.Column("external_order_id", sa.String(length=24), nullable=False),
        sa.Column("bitrix_buyer_user_id", sa.BigInteger(), nullable=True),
        sa.Column("promo_code", sa.String(length=120), nullable=False),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("currency", sa.String(length=8), server_default=sa.text("'RUB'"), nullable=False),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("period_start", sa.Date(), nullable=False),
        sa.Column("period_end", sa.Date(), nullable=False),
        sa.Column("bitrix_sync_status", sa.String(length=32), server_default=sa.text("'pending'"), nullable=False),
        sa.Column("bitrix_synced_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sync_error", sa.String(length=500), nullable=True),
        sa.Column(
            "calculation_snapshot",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["buyer_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["order_id"], ["orders.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("external_order_id"),
        sa.UniqueConstraint("order_id"),
    )
    for column in [
        "bitrix_buyer_user_id",
        "bitrix_sync_status",
        "buyer_user_id",
        "external_order_id",
        "id",
        "order_id",
        "paid_at",
        "period_end",
        "period_start",
        "promo_code",
    ]:
        op.create_index(
            f"ix_app_referral_purchases_{column}",
            "app_referral_purchases",
            [column],
            unique=False,
        )

    op.create_table(
        "app_referral_accruals",
        sa.Column("purchase_id", sa.BigInteger(), nullable=False),
        sa.Column("beneficiary_user_id", sa.BigInteger(), nullable=True),
        sa.Column("beneficiary_bitrix_user_id", sa.BigInteger(), nullable=False),
        sa.Column("beneficiary_email", sa.String(length=100), nullable=True),
        sa.Column("beneficiary_name", sa.String(length=255), nullable=True),
        sa.Column("referral_bitrix_user_id", sa.BigInteger(), nullable=False),
        sa.Column("level", sa.Integer(), nullable=False),
        sa.Column("buyer_discount_percent", sa.Numeric(7, 2), server_default=sa.text("0.00"), nullable=False),
        sa.Column("referrer_discount_percent", sa.Numeric(7, 2), server_default=sa.text("0.00"), nullable=False),
        sa.Column("commission_percent", sa.Numeric(7, 2), server_default=sa.text("0.00"), nullable=False),
        sa.Column("commission_amount", sa.Numeric(14, 2), server_default=sa.text("0.00"), nullable=False),
        sa.Column("currency", sa.String(length=8), server_default=sa.text("'RUB'"), nullable=False),
        sa.Column("status", sa.String(length=32), server_default=sa.text("'pending'"), nullable=False),
        sa.Column("reason", sa.String(length=255), nullable=True),
        sa.Column(
            "eligibility_snapshot",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["beneficiary_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["purchase_id"], ["app_referral_purchases.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("purchase_id", "level", name="uq_app_referral_accrual_purchase_level"),
    )
    for column in [
        "beneficiary_bitrix_user_id",
        "beneficiary_email",
        "beneficiary_user_id",
        "id",
        "purchase_id",
        "referral_bitrix_user_id",
        "status",
    ]:
        op.create_index(
            f"ix_app_referral_accruals_{column}",
            "app_referral_accruals",
            [column],
            unique=False,
        )


def downgrade() -> None:
    op.drop_table("app_referral_accruals")
    op.drop_table("app_referral_purchases")
