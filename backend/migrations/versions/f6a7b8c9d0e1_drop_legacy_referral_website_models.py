"""drop legacy referral, website, and deposit models

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-06-30 03:20:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "f6a7b8c9d0e1"
down_revision = "e5f6a7b8c9d0"
branch_labels = None
depends_on = None


def _table_exists(table_name: str) -> bool:
    return sa.inspect(op.get_bind()).has_table(table_name)


def _column_names(table_name: str) -> set[str]:
    if not _table_exists(table_name):
        return set()
    return {column["name"] for column in sa.inspect(op.get_bind()).get_columns(table_name)}


def _index_names(table_name: str) -> set[str | None]:
    if not _table_exists(table_name):
        return set()
    return {index["name"] for index in sa.inspect(op.get_bind()).get_indexes(table_name)}


def _drop_index_if_exists(table_name: str, index_name: str) -> None:
    if index_name in _index_names(table_name):
        op.drop_index(index_name, table_name=table_name)


def _drop_column_if_exists(table_name: str, column_name: str) -> None:
    if column_name in _column_names(table_name):
        op.drop_column(table_name, column_name)


def _drop_columns_if_exist(table_name: str, column_names: list[str]) -> None:
    for column_name in column_names:
        _drop_column_if_exists(table_name, column_name)


def _drop_table_if_exists(table_name: str) -> None:
    if _table_exists(table_name):
        op.drop_table(table_name)


def _add_column_if_missing(table_name: str, column: sa.Column) -> None:
    if _table_exists(table_name) and column.name not in _column_names(table_name):
        op.add_column(table_name, column)


def _create_index_if_missing(table_name: str, index_name: str, columns: list[str], *, unique: bool = False) -> None:
    if _table_exists(table_name) and index_name not in _index_names(table_name):
        op.create_index(index_name, table_name, columns, unique=unique)


def upgrade() -> None:
    for table_name, index_name in [
        ("order_benefit_applications", "ix_order_benefit_applications_website_identity_id"),
        ("order_benefit_applications", "ix_order_benefit_applications_referral_promo_code_id"),
        ("order_benefit_applications", "ix_order_benefit_applications_referral_relationship_id"),
        ("referral_profiles", "ix_referral_profiles_website_identity_id"),
        ("referral_profiles", "ix_referral_profiles_referrer_promo_code"),
        ("referral_profiles", "ix_referral_profiles_referrer_user_id"),
    ]:
        _drop_index_if_exists(table_name, index_name)

    _drop_columns_if_exist(
        "order_benefit_applications",
        [
            "website_identity_id",
            "website_coupon_id",
            "website_discount_entitlement_id",
            "website_bonus_account_id",
            "app_promo_id",
            "resolved_referrer_website_user_id",
            "referral_promo_code_id",
            "referral_relationship_id",
            "bonus_spent_amount",
        ],
    )
    _drop_columns_if_exist(
        "referral_profiles",
        [
            "website_identity_id",
            "website_seed_purchase_balance",
            "website_seed_payload",
            "website_seeded_at",
            "initial_purchase_balance",
            "app_paid_purchase_total",
            "current_month_purchase_total",
            "previous_month_purchase_total",
            "referrer_promo_code",
            "referrer_user_id",
            "referrer_attached_at",
            "promo_changed_at",
            "own_promo_code",
            "own_promo_issued_at",
        ],
    )

    for table_name in [
        "business_ledger_entries",
        "referral_commission_entries",
        "referral_relationships",
        "referral_promo_codes",
        "website_sync_events",
        "website_coupons",
        "website_discount_entitlements",
        "website_bonus_accounts",
        "website_referral_profiles",
        "website_identities",
        "app_promos",
    ]:
        _drop_table_if_exists(table_name)


def _website_identity_columns() -> list[sa.Column]:
    return [
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("website_user_id", sa.BigInteger(), nullable=False),
        sa.Column("website_login", sa.String(length=120), nullable=False, server_default=""),
        sa.Column("website_email", sa.String(length=190), nullable=True),
        sa.Column("website_name", sa.String(length=120), nullable=True),
        sa.Column("website_last_name", sa.String(length=120), nullable=True),
        sa.Column("website_second_name", sa.String(length=120), nullable=True),
        sa.Column("website_phone", sa.String(length=80), nullable=True),
        sa.Column("website_mobile", sa.String(length=80), nullable=True),
        sa.Column("website_city", sa.String(length=120), nullable=True),
        sa.Column("website_registered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("website_last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("group_ids", sa.JSON(), nullable=False, server_default=sa.text("'[]'::json")),
        sa.Column("group_names", sa.JSON(), nullable=False, server_default=sa.text("'[]'::json")),
        sa.Column("custom_fields", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column("referral_program", sa.JSON(), nullable=True),
        sa.Column("bonus_account", sa.JSON(), nullable=True),
        sa.Column("discount_groups", sa.JSON(), nullable=False, server_default=sa.text("'[]'::json")),
        sa.Column("active_coupons", sa.JSON(), nullable=False, server_default=sa.text("'[]'::json")),
        sa.Column("recent_used_coupons", sa.JSON(), nullable=False, server_default=sa.text("'[]'::json")),
        sa.Column("raw_payload", sa.JSON(), nullable=True),
        sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    ]


def downgrade() -> None:
    if not _table_exists("website_identities"):
        op.create_table(
            "website_identities",
            *_website_identity_columns(),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        _create_index_if_missing("website_identities", "ix_website_identities_id", ["id"])
        _create_index_if_missing("website_identities", "ix_website_identities_user_id", ["user_id"], unique=True)
        _create_index_if_missing("website_identities", "ix_website_identities_website_user_id", ["website_user_id"], unique=True)

    if not _table_exists("referral_promo_codes"):
        op.create_table(
            "referral_promo_codes",
            sa.Column("code", sa.String(length=120), nullable=False),
            sa.Column("owner_user_id", sa.BigInteger(), nullable=False),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
            sa.Column("source_system", sa.String(length=48), nullable=False, server_default=sa.text("'app'")),
            sa.Column("issued_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["owner_user_id"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("code"),
        )
        _create_index_if_missing("referral_promo_codes", "ix_referral_promo_codes_code", ["code"])
        _create_index_if_missing("referral_promo_codes", "ix_referral_promo_codes_id", ["id"])
        _create_index_if_missing("referral_promo_codes", "ix_referral_promo_codes_is_active", ["is_active"])
        _create_index_if_missing("referral_promo_codes", "ix_referral_promo_codes_owner_user_id", ["owner_user_id"])

    if not _table_exists("referral_relationships"):
        op.create_table(
            "referral_relationships",
            sa.Column("referred_user_id", sa.BigInteger(), nullable=False),
            sa.Column("referrer_user_id", sa.BigInteger(), nullable=True),
            sa.Column("referral_promo_code_id", sa.BigInteger(), nullable=True),
            sa.Column("referrer_promo_code", sa.String(length=120), nullable=False),
            sa.Column("depth", sa.Integer(), nullable=False, server_default=sa.text("2")),
            sa.Column("source_system", sa.String(length=48), nullable=False, server_default=sa.text("'app'")),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
            sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("replaced_by_relationship_id", sa.BigInteger(), nullable=True),
            sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["referral_promo_code_id"], ["referral_promo_codes.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["referred_user_id"], ["users.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["referrer_user_id"], ["users.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["replaced_by_relationship_id"], ["referral_relationships.id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("id"),
        )
        _create_index_if_missing("referral_relationships", "ix_referral_relationships_id", ["id"])
        _create_index_if_missing("referral_relationships", "ix_referral_relationships_is_active", ["is_active"])
        _create_index_if_missing("referral_relationships", "ix_referral_relationships_referral_promo_code_id", ["referral_promo_code_id"])
        _create_index_if_missing("referral_relationships", "ix_referral_relationships_referred_user_id", ["referred_user_id"])
        _create_index_if_missing("referral_relationships", "ix_referral_relationships_referrer_promo_code", ["referrer_promo_code"])
        _create_index_if_missing("referral_relationships", "ix_referral_relationships_referrer_user_id", ["referrer_user_id"])

    if not _table_exists("website_referral_profiles"):
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
        _create_index_if_missing("website_referral_profiles", "ix_website_referral_profiles_id", ["id"])
        _create_index_if_missing("website_referral_profiles", "ix_website_referral_profiles_own_promo_code", ["own_promo_code"])
        _create_index_if_missing("website_referral_profiles", "ix_website_referral_profiles_referrer_website_user_id", ["referrer_website_user_id"])

    if not _table_exists("website_bonus_accounts"):
        op.create_table(
            "website_bonus_accounts",
            sa.Column("website_identity_id", sa.BigInteger(), nullable=False),
            sa.Column("website_bonus_account_external_id", sa.BigInteger(), nullable=True),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
            sa.Column("balance", sa.Numeric(14, 2), nullable=False, server_default=sa.text("0.00")),
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
        _create_index_if_missing("website_bonus_accounts", "ix_website_bonus_accounts_id", ["id"])

    if not _table_exists("website_discount_entitlements"):
        op.create_table(
            "website_discount_entitlements",
            sa.Column("website_identity_id", sa.BigInteger(), nullable=False),
            sa.Column("source_kind", sa.String(length=48), nullable=False, server_default=sa.text("'group'")),
            sa.Column("website_source_id", sa.String(length=128), nullable=True),
            sa.Column("source_name", sa.String(length=255), nullable=False),
            sa.Column("discount_percent", sa.Numeric(7, 2), nullable=True),
            sa.Column("discount_amount", sa.Numeric(14, 2), nullable=True),
            sa.Column("currency", sa.String(length=8), nullable=True),
            sa.Column("priority", sa.Integer(), nullable=True),
            sa.Column("is_stackable", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
            sa.Column("starts_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("ends_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["website_identity_id"], ["website_identities.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("website_identity_id", "source_kind", "website_source_id", name="uq_website_discount_entitlements_identity_source"),
        )
        _create_index_if_missing("website_discount_entitlements", "ix_website_discount_entitlements_id", ["id"])
        _create_index_if_missing("website_discount_entitlements", "ix_website_discount_entitlements_website_identity_id", ["website_identity_id"])

    if not _table_exists("website_coupons"):
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
            sa.Column("use_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
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
        _create_index_if_missing("website_coupons", "ix_website_coupons_coupon_code", ["coupon_code"])
        _create_index_if_missing("website_coupons", "ix_website_coupons_id", ["id"])
        _create_index_if_missing("website_coupons", "ix_website_coupons_website_identity_id", ["website_identity_id"])

    if not _table_exists("app_promos"):
        op.create_table(
            "app_promos",
            sa.Column("code", sa.String(length=120), nullable=False),
            sa.Column("name", sa.String(length=255), nullable=False),
            sa.Column("source_kind", sa.String(length=48), nullable=False, server_default=sa.text("'app'")),
            sa.Column("benefit_kind", sa.String(length=48), nullable=False),
            sa.Column("discount_percent", sa.Numeric(7, 2), nullable=True),
            sa.Column("discount_amount", sa.Numeric(14, 2), nullable=True),
            sa.Column("currency", sa.String(length=8), nullable=True),
            sa.Column("starts_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("ends_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
            sa.Column("max_total_uses", sa.Integer(), nullable=True),
            sa.Column("max_uses_per_user", sa.Integer(), nullable=True),
            sa.Column("stacking_policy", sa.String(length=48), nullable=False, server_default=sa.text("'exclusive'")),
            sa.Column("created_by_user_id", sa.BigInteger(), nullable=True),
            sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("code"),
        )
        _create_index_if_missing("app_promos", "ix_app_promos_created_by_user_id", ["created_by_user_id"])
        _create_index_if_missing("app_promos", "ix_app_promos_id", ["id"])

    if not _table_exists("referral_commission_entries"):
        op.create_table(
            "referral_commission_entries",
            sa.Column("period_start", sa.Date(), nullable=False),
            sa.Column("period_end", sa.Date(), nullable=False),
            sa.Column("order_id", sa.BigInteger(), nullable=False),
            sa.Column("buyer_user_id", sa.BigInteger(), nullable=True),
            sa.Column("referrer_user_id", sa.BigInteger(), nullable=True),
            sa.Column("referral_relationship_id", sa.BigInteger(), nullable=True),
            sa.Column("level", sa.Integer(), nullable=False),
            sa.Column("promo_code", sa.String(length=120), nullable=True),
            sa.Column("buyer_discount_percent", sa.Numeric(7, 2), nullable=False, server_default=sa.text("0.00")),
            sa.Column("referrer_discount_percent", sa.Numeric(7, 2), nullable=False, server_default=sa.text("0.00")),
            sa.Column("commission_percent", sa.Numeric(7, 2), nullable=False, server_default=sa.text("0.00")),
            sa.Column("order_subtotal", sa.Numeric(14, 2), nullable=False, server_default=sa.text("0.00")),
            sa.Column("commission_amount", sa.Numeric(14, 2), nullable=False, server_default=sa.text("0.00")),
            sa.Column("currency", sa.String(length=8), nullable=False, server_default=sa.text("'RUB'")),
            sa.Column("status", sa.String(length=32), nullable=False, server_default=sa.text("'posted'")),
            sa.Column("posted_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("idempotency_key", sa.String(length=128), nullable=False),
            sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["buyer_user_id"], ["users.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["order_id"], ["orders.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["referral_relationship_id"], ["referral_relationships.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["referrer_user_id"], ["users.id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("idempotency_key"),
        )
        for column in ["buyer_user_id", "id", "order_id", "period_end", "period_start", "promo_code", "referral_relationship_id", "referrer_user_id", "status"]:
            _create_index_if_missing("referral_commission_entries", f"ix_referral_commission_entries_{column}", [column])

    if not _table_exists("business_ledger_entries"):
        op.create_table(
            "business_ledger_entries",
            sa.Column("order_id", sa.BigInteger(), nullable=True),
            sa.Column("order_benefit_application_id", sa.BigInteger(), nullable=True),
            sa.Column("referral_commission_entry_id", sa.BigInteger(), nullable=True),
            sa.Column("user_id", sa.BigInteger(), nullable=True),
            sa.Column("website_identity_id", sa.BigInteger(), nullable=True),
            sa.Column("entry_type", sa.String(length=48), nullable=False),
            sa.Column("direction", sa.String(length=48), nullable=False),
            sa.Column("amount", sa.Numeric(14, 2), nullable=False),
            sa.Column("currency", sa.String(length=8), nullable=False),
            sa.Column("source_system", sa.String(length=48), nullable=False),
            sa.Column("source_code", sa.String(length=120), nullable=True),
            sa.Column("status", sa.String(length=32), nullable=False, server_default=sa.text("'posted'")),
            sa.Column("effective_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("note", sa.String(length=500), nullable=True),
            sa.Column("idempotency_key", sa.String(length=128), nullable=True),
            sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["order_benefit_application_id"], ["order_benefit_applications.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["referral_commission_entry_id"], ["referral_commission_entries.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["website_identity_id"], ["website_identities.id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("idempotency_key"),
        )
        for column in ["id", "order_id", "order_benefit_application_id", "referral_commission_entry_id", "user_id", "website_identity_id"]:
            _create_index_if_missing("business_ledger_entries", f"ix_business_ledger_entries_{column}", [column])

    if not _table_exists("website_sync_events"):
        op.create_table(
            "website_sync_events",
            sa.Column("order_id", sa.BigInteger(), nullable=True),
            sa.Column("user_id", sa.BigInteger(), nullable=True),
            sa.Column("website_identity_id", sa.BigInteger(), nullable=True),
            sa.Column("event_type", sa.String(length=48), nullable=False),
            sa.Column("external_order_id", sa.String(length=128), nullable=True),
            sa.Column("request_payload", sa.JSON(), nullable=True),
            sa.Column("response_payload", sa.JSON(), nullable=True),
            sa.Column("status", sa.String(length=32), nullable=False, server_default=sa.text("'pending'")),
            sa.Column("error_message", sa.String(length=500), nullable=True),
            sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["website_identity_id"], ["website_identities.id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("id"),
        )
        for column in ["event_type", "external_order_id", "id", "order_id", "status", "user_id", "website_identity_id"]:
            _create_index_if_missing("website_sync_events", f"ix_website_sync_events_{column}", [column])

    _add_column_if_missing("referral_profiles", sa.Column("website_identity_id", sa.BigInteger(), sa.ForeignKey("website_identities.id", ondelete="SET NULL"), nullable=True))
    _add_column_if_missing("referral_profiles", sa.Column("initial_purchase_balance", sa.Numeric(14, 2), nullable=False, server_default=sa.text("0.00")))
    _add_column_if_missing("referral_profiles", sa.Column("website_seed_purchase_balance", sa.Numeric(14, 2), nullable=False, server_default=sa.text("0.00")))
    _add_column_if_missing("referral_profiles", sa.Column("app_paid_purchase_total", sa.Numeric(14, 2), nullable=False, server_default=sa.text("0.00")))
    _add_column_if_missing("referral_profiles", sa.Column("current_month_purchase_total", sa.Numeric(14, 2), nullable=False, server_default=sa.text("0.00")))
    _add_column_if_missing("referral_profiles", sa.Column("previous_month_purchase_total", sa.Numeric(14, 2), nullable=False, server_default=sa.text("0.00")))
    _add_column_if_missing("referral_profiles", sa.Column("referrer_promo_code", sa.String(length=120), nullable=True))
    _add_column_if_missing("referral_profiles", sa.Column("referrer_user_id", sa.BigInteger(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True))
    _add_column_if_missing("referral_profiles", sa.Column("referrer_attached_at", sa.DateTime(timezone=True), nullable=True))
    _add_column_if_missing("referral_profiles", sa.Column("promo_changed_at", sa.DateTime(timezone=True), nullable=True))
    _add_column_if_missing("referral_profiles", sa.Column("own_promo_code", sa.String(length=120), nullable=True))
    _add_column_if_missing("referral_profiles", sa.Column("own_promo_issued_at", sa.DateTime(timezone=True), nullable=True))
    _add_column_if_missing("referral_profiles", sa.Column("website_seed_payload", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")))
    _add_column_if_missing("referral_profiles", sa.Column("website_seeded_at", sa.DateTime(timezone=True), nullable=True))
    _create_index_if_missing("referral_profiles", "ix_referral_profiles_website_identity_id", ["website_identity_id"])
    _create_index_if_missing("referral_profiles", "ix_referral_profiles_referrer_promo_code", ["referrer_promo_code"])
    _create_index_if_missing("referral_profiles", "ix_referral_profiles_referrer_user_id", ["referrer_user_id"])

    _add_column_if_missing("order_benefit_applications", sa.Column("website_identity_id", sa.BigInteger(), sa.ForeignKey("website_identities.id", ondelete="SET NULL"), nullable=True))
    _add_column_if_missing("order_benefit_applications", sa.Column("website_coupon_id", sa.BigInteger(), sa.ForeignKey("website_coupons.id", ondelete="SET NULL"), nullable=True))
    _add_column_if_missing("order_benefit_applications", sa.Column("website_discount_entitlement_id", sa.BigInteger(), sa.ForeignKey("website_discount_entitlements.id", ondelete="SET NULL"), nullable=True))
    _add_column_if_missing("order_benefit_applications", sa.Column("website_bonus_account_id", sa.BigInteger(), sa.ForeignKey("website_bonus_accounts.id", ondelete="SET NULL"), nullable=True))
    _add_column_if_missing("order_benefit_applications", sa.Column("app_promo_id", sa.BigInteger(), sa.ForeignKey("app_promos.id", ondelete="SET NULL"), nullable=True))
    _add_column_if_missing("order_benefit_applications", sa.Column("resolved_referrer_website_user_id", sa.BigInteger(), nullable=True))
    _add_column_if_missing("order_benefit_applications", sa.Column("referral_promo_code_id", sa.BigInteger(), sa.ForeignKey("referral_promo_codes.id", ondelete="SET NULL"), nullable=True))
    _add_column_if_missing("order_benefit_applications", sa.Column("referral_relationship_id", sa.BigInteger(), sa.ForeignKey("referral_relationships.id", ondelete="SET NULL"), nullable=True))
    _add_column_if_missing("order_benefit_applications", sa.Column("bonus_spent_amount", sa.Numeric(14, 2), nullable=True))
    _create_index_if_missing("order_benefit_applications", "ix_order_benefit_applications_website_identity_id", ["website_identity_id"])
    _create_index_if_missing("order_benefit_applications", "ix_order_benefit_applications_referral_promo_code_id", ["referral_promo_code_id"])
    _create_index_if_missing("order_benefit_applications", "ix_order_benefit_applications_referral_relationship_id", ["referral_relationship_id"])
