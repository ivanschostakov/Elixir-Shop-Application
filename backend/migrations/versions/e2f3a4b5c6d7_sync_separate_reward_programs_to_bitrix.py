"""add mutually exclusive reward programs and partner sync audit

Revision ID: e2f3a4b5c6d7
Revises: d1e2f3a4b5c6
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "e2f3a4b5c6d7"
down_revision: str | Sequence[str] | None = "d1e2f3a4b5c6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "referral_profiles",
        sa.Column("reward_program", sa.String(length=16), nullable=True),
    )
    op.add_column(
        "referral_profiles",
        sa.Column("reward_program_selected_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "referral_profiles",
        sa.Column("reward_program_selection_source", sa.String(length=32), nullable=True),
    )
    op.add_column(
        "referral_profiles",
        sa.Column(
            "reward_program_snapshot",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
    )
    op.add_column(
        "referral_profiles",
        sa.Column("bitrix_user_id", sa.BigInteger(), nullable=True),
    )
    op.create_index(
        "ix_referral_profiles_reward_program",
        "referral_profiles",
        ["reward_program"],
        unique=False,
    )
    op.create_index(
        "ix_referral_profiles_bitrix_user_id",
        "referral_profiles",
        ["bitrix_user_id"],
        unique=False,
    )

    op.create_table(
        "reward_program_selection_events",
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("previous_program", sa.String(length=16), nullable=True),
        sa.Column("selected_program", sa.String(length=16), nullable=False),
        sa.Column("source", sa.String(length=32), server_default=sa.text("'user'"), nullable=False),
        sa.Column("reason", sa.String(length=500), nullable=True),
        sa.Column("selected_by_admin_user_id", sa.BigInteger(), nullable=True),
        sa.Column(
            "snapshot",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in ("id", "user_id", "selected_program", "selected_by_admin_user_id"):
        op.create_index(
            f"ix_reward_program_selection_events_{column}",
            "reward_program_selection_events",
            [column],
            unique=False,
        )

    op.create_table(
        "bonus_program_purchases",
        sa.Column("order_id", sa.BigInteger(), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=True),
        sa.Column("external_order_id", sa.String(length=24), nullable=False),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("currency", sa.String(length=8), server_default=sa.text("'RUB'"), nullable=False),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(length=32), server_default=sa.text("'posted'"), nullable=False),
        sa.Column("reversed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "calculation_snapshot",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["order_id"], ["orders.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("external_order_id"),
        sa.UniqueConstraint("order_id"),
    )
    for column in ("id", "order_id", "user_id", "external_order_id", "paid_at", "status"):
        op.create_index(
            f"ix_bonus_program_purchases_{column}",
            "bonus_program_purchases",
            [column],
            unique=False,
        )

    op.alter_column(
        "app_referral_purchases",
        "promo_code",
        existing_type=sa.String(length=120),
        nullable=True,
    )
    op.add_column(
        "app_referral_purchases",
        sa.Column("bitrix_purchase_id", sa.BigInteger(), nullable=True),
    )
    op.add_column(
        "app_referral_purchases",
        sa.Column("bitrix_coupon_id", sa.BigInteger(), nullable=True),
    )
    op.add_column(
        "app_referral_purchases",
        sa.Column("bitrix_discount_id", sa.BigInteger(), nullable=True),
    )
    op.add_column(
        "app_referral_purchases",
        sa.Column("coupon_use_count_before", sa.Integer(), nullable=True),
    )
    op.add_column(
        "app_referral_purchases",
        sa.Column("coupon_use_count_after", sa.Integer(), nullable=True),
    )
    op.add_column(
        "app_referral_purchases",
        sa.Column("status", sa.String(length=32), server_default=sa.text("'posted'"), nullable=False),
    )
    op.add_column(
        "app_referral_purchases",
        sa.Column("reversed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_app_referral_purchases_bitrix_purchase_id",
        "app_referral_purchases",
        ["bitrix_purchase_id"],
        unique=False,
    )
    for column in ("bitrix_coupon_id", "bitrix_discount_id", "status"):
        op.create_index(
            f"ix_app_referral_purchases_{column}",
            "app_referral_purchases",
            [column],
            unique=False,
        )
    op.add_column(
        "app_referral_accruals",
        sa.Column("bitrix_accrual_id", sa.BigInteger(), nullable=True),
    )
    op.create_index(
        "ix_app_referral_accruals_bitrix_accrual_id",
        "app_referral_accruals",
        ["bitrix_accrual_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_app_referral_accruals_bitrix_accrual_id",
        table_name="app_referral_accruals",
    )
    op.drop_column("app_referral_accruals", "bitrix_accrual_id")
    for column in ("status", "bitrix_discount_id", "bitrix_coupon_id"):
        op.drop_index(
            f"ix_app_referral_purchases_{column}",
            table_name="app_referral_purchases",
        )
    op.drop_index(
        "ix_app_referral_purchases_bitrix_purchase_id",
        table_name="app_referral_purchases",
    )
    op.drop_column("app_referral_purchases", "reversed_at")
    op.drop_column("app_referral_purchases", "status")
    op.drop_column("app_referral_purchases", "coupon_use_count_after")
    op.drop_column("app_referral_purchases", "coupon_use_count_before")
    op.drop_column("app_referral_purchases", "bitrix_discount_id")
    op.drop_column("app_referral_purchases", "bitrix_coupon_id")
    op.drop_column("app_referral_purchases", "bitrix_purchase_id")
    op.execute(
        "UPDATE app_referral_purchases SET promo_code = '' WHERE promo_code IS NULL"
    )
    op.alter_column(
        "app_referral_purchases",
        "promo_code",
        existing_type=sa.String(length=120),
        nullable=False,
    )
    op.drop_table("bonus_program_purchases")
    op.drop_table("reward_program_selection_events")
    op.drop_index("ix_referral_profiles_bitrix_user_id", table_name="referral_profiles")
    op.drop_index("ix_referral_profiles_reward_program", table_name="referral_profiles")
    op.drop_column("referral_profiles", "bitrix_user_id")
    op.drop_column("referral_profiles", "reward_program_snapshot")
    op.drop_column("referral_profiles", "reward_program_selection_source")
    op.drop_column("referral_profiles", "reward_program_selected_at")
    op.drop_column("referral_profiles", "reward_program")
