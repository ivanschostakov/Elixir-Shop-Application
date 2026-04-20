"""add business tables for website sync and gains

Revision ID: 7a9c4d1e2b3f
Revises: 64b0f8d6b6ec
Create Date: 2026-04-08 18:30:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "7a9c4d1e2b3f"
down_revision: Union[str, Sequence[str], None] = "64b0f8d6b6ec"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "website_referral_profiles",
        sa.Column("website_identity_id", sa.BigInteger(), nullable=False),
        sa.Column("own_promo_code", sa.String(length=120), nullable=True),
        sa.Column("referrer_website_user_id", sa.BigInteger(), nullable=True),
        sa.Column("referrer_promo_code", sa.String(length=120), nullable=True),
        sa.Column("referral_percent", sa.Numeric(7, 2), nullable=True),
        sa.Column("referral_turnover_amount", sa.Numeric(14, 2), nullable=True),
        sa.Column("referral_turnover_currency", sa.String(length=8), nullable=True),
        sa.Column("monthly_paid_orders_amount", sa.Numeric(14, 2), nullable=True),
        sa.Column("monthly_paid_orders_currency", sa.String(length=8), nullable=True),
        sa.Column("tier_group_id", sa.BigInteger(), nullable=True),
        sa.Column("tier_group_name", sa.String(length=255), nullable=True),
        sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["website_identity_id"], ["website_identities.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("website_identity_id"),
    )
    op.create_index(op.f("ix_website_referral_profiles_id"), "website_referral_profiles", ["id"], unique=False)
    op.create_index(op.f("ix_website_referral_profiles_own_promo_code"), "website_referral_profiles", ["own_promo_code"], unique=False)
    op.create_index(
        op.f("ix_website_referral_profiles_referrer_website_user_id"),
        "website_referral_profiles",
        ["referrer_website_user_id"],
        unique=False,
    )

    op.create_table(
        "website_bonus_accounts",
        sa.Column("website_identity_id", sa.BigInteger(), nullable=False),
        sa.Column("website_bonus_account_external_id", sa.BigInteger(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("balance", sa.Numeric(14, 2), nullable=False),
        sa.Column("currency", sa.String(length=8), nullable=True),
        sa.Column("website_created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["website_identity_id"], ["website_identities.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("website_bonus_account_external_id"),
        sa.UniqueConstraint("website_identity_id"),
    )
    op.create_index(op.f("ix_website_bonus_accounts_id"), "website_bonus_accounts", ["id"], unique=False)

    op.create_table(
        "website_discount_entitlements",
        sa.Column("website_identity_id", sa.BigInteger(), nullable=False),
        sa.Column("source_kind", sa.String(length=48), nullable=False),
        sa.Column("website_source_id", sa.String(length=128), nullable=True),
        sa.Column("source_name", sa.String(length=255), nullable=False),
        sa.Column("discount_percent", sa.Numeric(7, 2), nullable=True),
        sa.Column("discount_amount", sa.Numeric(14, 2), nullable=True),
        sa.Column("currency", sa.String(length=8), nullable=True),
        sa.Column("priority", sa.Integer(), nullable=True),
        sa.Column("is_stackable", sa.Boolean(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["website_identity_id"], ["website_identities.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "website_identity_id", "source_kind", "website_source_id", name="uq_website_discount_entitlements_identity_source"
        ),
    )
    op.create_index(op.f("ix_website_discount_entitlements_id"), "website_discount_entitlements", ["id"], unique=False)
    op.create_index(
        op.f("ix_website_discount_entitlements_website_identity_id"), "website_discount_entitlements", ["website_identity_id"], unique=False
    )

    op.create_table(
        "website_coupons",
        sa.Column("website_identity_id", sa.BigInteger(), nullable=False),
        sa.Column("website_coupon_external_id", sa.BigInteger(), nullable=True),
        sa.Column("coupon_code", sa.String(length=120), nullable=False),
        sa.Column("discount_rule_id", sa.BigInteger(), nullable=True),
        sa.Column("discount_rule_name", sa.String(length=255), nullable=True),
        sa.Column("discount_type", sa.String(length=48), nullable=True),
        sa.Column("discount_value", sa.Numeric(14, 2), nullable=True),
        sa.Column("discount_currency", sa.String(length=8), nullable=True),
        sa.Column("max_use", sa.Integer(), nullable=True),
        sa.Column("use_count", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("description", sa.String(length=500), nullable=True),
        sa.Column("website_created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("website_applied_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["website_identity_id"], ["website_identities.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("website_coupon_external_id"),
    )
    op.create_index(op.f("ix_website_coupons_coupon_code"), "website_coupons", ["coupon_code"], unique=False)
    op.create_index(op.f("ix_website_coupons_id"), "website_coupons", ["id"], unique=False)
    op.create_index(op.f("ix_website_coupons_website_identity_id"), "website_coupons", ["website_identity_id"], unique=False)

    op.create_table(
        "app_promos",
        sa.Column("code", sa.String(length=120), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("source_kind", sa.String(length=48), nullable=False),
        sa.Column("benefit_kind", sa.String(length=48), nullable=False),
        sa.Column("discount_percent", sa.Numeric(7, 2), nullable=True),
        sa.Column("discount_amount", sa.Numeric(14, 2), nullable=True),
        sa.Column("currency", sa.String(length=8), nullable=True),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("max_total_uses", sa.Integer(), nullable=True),
        sa.Column("max_uses_per_user", sa.Integer(), nullable=True),
        sa.Column("stacking_policy", sa.String(length=48), nullable=False),
        sa.Column("created_by_user_id", sa.BigInteger(), nullable=True),
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code"),
    )
    op.create_index(op.f("ix_app_promos_created_by_user_id"), "app_promos", ["created_by_user_id"], unique=False)
    op.create_index(op.f("ix_app_promos_id"), "app_promos", ["id"], unique=False)

    op.create_table(
        "order_benefit_applications",
        sa.Column("order_id", sa.BigInteger(), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=True),
        sa.Column("website_identity_id", sa.BigInteger(), nullable=True),
        sa.Column("source_kind", sa.String(length=48), nullable=False),
        sa.Column("website_coupon_id", sa.BigInteger(), nullable=True),
        sa.Column("website_discount_entitlement_id", sa.BigInteger(), nullable=True),
        sa.Column("website_bonus_account_id", sa.BigInteger(), nullable=True),
        sa.Column("app_promo_id", sa.BigInteger(), nullable=True),
        sa.Column("entered_code", sa.String(length=120), nullable=True),
        sa.Column("resolved_code", sa.String(length=120), nullable=True),
        sa.Column("resolved_referrer_website_user_id", sa.BigInteger(), nullable=True),
        sa.Column("discount_percent", sa.Numeric(7, 2), nullable=True),
        sa.Column("discount_amount", sa.Numeric(14, 2), nullable=True),
        sa.Column("bonus_spent_amount", sa.Numeric(14, 2), nullable=True),
        sa.Column("currency", sa.String(length=8), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("applied_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["app_promo_id"], ["app_promos.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["website_bonus_account_id"], ["website_bonus_accounts.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["website_coupon_id"], ["website_coupons.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["website_discount_entitlement_id"], ["website_discount_entitlements.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["website_identity_id"], ["website_identities.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_order_benefit_applications_id"), "order_benefit_applications", ["id"], unique=False)
    op.create_index(op.f("ix_order_benefit_applications_order_id"), "order_benefit_applications", ["order_id"], unique=False)
    op.create_index(op.f("ix_order_benefit_applications_source_kind"), "order_benefit_applications", ["source_kind"], unique=False)
    op.create_index(op.f("ix_order_benefit_applications_status"), "order_benefit_applications", ["status"], unique=False)
    op.create_index(op.f("ix_order_benefit_applications_user_id"), "order_benefit_applications", ["user_id"], unique=False)
    op.create_index(
        op.f("ix_order_benefit_applications_website_identity_id"), "order_benefit_applications", ["website_identity_id"], unique=False
    )

    op.create_table(
        "business_ledger_entries",
        sa.Column("order_id", sa.BigInteger(), nullable=True),
        sa.Column("order_benefit_application_id", sa.BigInteger(), nullable=True),
        sa.Column("user_id", sa.BigInteger(), nullable=True),
        sa.Column("website_identity_id", sa.BigInteger(), nullable=True),
        sa.Column("entry_type", sa.String(length=48), nullable=False),
        sa.Column("direction", sa.String(length=48), nullable=False),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("currency", sa.String(length=8), nullable=False),
        sa.Column("source_system", sa.String(length=48), nullable=False),
        sa.Column("source_code", sa.String(length=120), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("effective_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("note", sa.String(length=500), nullable=True),
        sa.Column("idempotency_key", sa.String(length=128), nullable=True),
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["order_benefit_application_id"], ["order_benefit_applications.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["website_identity_id"], ["website_identities.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("idempotency_key"),
    )
    op.create_index(op.f("ix_business_ledger_entries_id"), "business_ledger_entries", ["id"], unique=False)
    op.create_index(op.f("ix_business_ledger_entries_order_id"), "business_ledger_entries", ["order_id"], unique=False)
    op.create_index(
        op.f("ix_business_ledger_entries_order_benefit_application_id"),
        "business_ledger_entries",
        ["order_benefit_application_id"],
        unique=False,
    )
    op.create_index(op.f("ix_business_ledger_entries_user_id"), "business_ledger_entries", ["user_id"], unique=False)
    op.create_index(
        op.f("ix_business_ledger_entries_website_identity_id"), "business_ledger_entries", ["website_identity_id"], unique=False
    )

    op.create_table(
        "website_sync_events",
        sa.Column("order_id", sa.BigInteger(), nullable=True),
        sa.Column("user_id", sa.BigInteger(), nullable=True),
        sa.Column("website_identity_id", sa.BigInteger(), nullable=True),
        sa.Column("event_type", sa.String(length=48), nullable=False),
        sa.Column("external_order_id", sa.String(length=128), nullable=True),
        sa.Column("request_payload", sa.JSON(), nullable=True),
        sa.Column("response_payload", sa.JSON(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("error_message", sa.String(length=500), nullable=True),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["website_identity_id"], ["website_identities.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_website_sync_events_event_type"), "website_sync_events", ["event_type"], unique=False)
    op.create_index(op.f("ix_website_sync_events_external_order_id"), "website_sync_events", ["external_order_id"], unique=False)
    op.create_index(op.f("ix_website_sync_events_id"), "website_sync_events", ["id"], unique=False)
    op.create_index(op.f("ix_website_sync_events_order_id"), "website_sync_events", ["order_id"], unique=False)
    op.create_index(op.f("ix_website_sync_events_status"), "website_sync_events", ["status"], unique=False)
    op.create_index(op.f("ix_website_sync_events_user_id"), "website_sync_events", ["user_id"], unique=False)
    op.create_index(op.f("ix_website_sync_events_website_identity_id"), "website_sync_events", ["website_identity_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_website_sync_events_website_identity_id"), table_name="website_sync_events")
    op.drop_index(op.f("ix_website_sync_events_user_id"), table_name="website_sync_events")
    op.drop_index(op.f("ix_website_sync_events_status"), table_name="website_sync_events")
    op.drop_index(op.f("ix_website_sync_events_order_id"), table_name="website_sync_events")
    op.drop_index(op.f("ix_website_sync_events_id"), table_name="website_sync_events")
    op.drop_index(op.f("ix_website_sync_events_external_order_id"), table_name="website_sync_events")
    op.drop_index(op.f("ix_website_sync_events_event_type"), table_name="website_sync_events")
    op.drop_table("website_sync_events")

    op.drop_index(op.f("ix_business_ledger_entries_website_identity_id"), table_name="business_ledger_entries")
    op.drop_index(op.f("ix_business_ledger_entries_user_id"), table_name="business_ledger_entries")
    op.drop_index(op.f("ix_business_ledger_entries_order_benefit_application_id"), table_name="business_ledger_entries")
    op.drop_index(op.f("ix_business_ledger_entries_id"), table_name="business_ledger_entries")
    op.drop_index(op.f("ix_business_ledger_entries_order_id"), table_name="business_ledger_entries")
    op.drop_table("business_ledger_entries")

    op.drop_index(op.f("ix_order_benefit_applications_website_identity_id"), table_name="order_benefit_applications")
    op.drop_index(op.f("ix_order_benefit_applications_user_id"), table_name="order_benefit_applications")
    op.drop_index(op.f("ix_order_benefit_applications_status"), table_name="order_benefit_applications")
    op.drop_index(op.f("ix_order_benefit_applications_source_kind"), table_name="order_benefit_applications")
    op.drop_index(op.f("ix_order_benefit_applications_order_id"), table_name="order_benefit_applications")
    op.drop_index(op.f("ix_order_benefit_applications_id"), table_name="order_benefit_applications")
    op.drop_table("order_benefit_applications")

    op.drop_index(op.f("ix_app_promos_id"), table_name="app_promos")
    op.drop_index(op.f("ix_app_promos_created_by_user_id"), table_name="app_promos")
    op.drop_table("app_promos")

    op.drop_index(op.f("ix_website_coupons_website_identity_id"), table_name="website_coupons")
    op.drop_index(op.f("ix_website_coupons_id"), table_name="website_coupons")
    op.drop_index(op.f("ix_website_coupons_coupon_code"), table_name="website_coupons")
    op.drop_table("website_coupons")

    op.drop_index(op.f("ix_website_discount_entitlements_website_identity_id"), table_name="website_discount_entitlements")
    op.drop_index(op.f("ix_website_discount_entitlements_id"), table_name="website_discount_entitlements")
    op.drop_table("website_discount_entitlements")

    op.drop_index(op.f("ix_website_bonus_accounts_id"), table_name="website_bonus_accounts")
    op.drop_table("website_bonus_accounts")

    op.drop_index(op.f("ix_website_referral_profiles_referrer_website_user_id"), table_name="website_referral_profiles")
    op.drop_index(op.f("ix_website_referral_profiles_own_promo_code"), table_name="website_referral_profiles")
    op.drop_index(op.f("ix_website_referral_profiles_id"), table_name="website_referral_profiles")
    op.drop_table("website_referral_profiles")
