"""add app referral system

Revision ID: e9a4f2c8d7b1
Revises: d8e9f0a1b2c3
Create Date: 2026-05-06 12:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "e9a4f2c8d7b1"
down_revision: Union[str, Sequence[str], None] = "d8e9f0a1b2c3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "referral_profiles",
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("website_identity_id", sa.BigInteger(), nullable=True),
        sa.Column("initial_purchase_balance", sa.Numeric(14, 2), nullable=False, server_default=sa.text("0.00")),
        sa.Column("website_seed_purchase_balance", sa.Numeric(14, 2), nullable=False, server_default=sa.text("0.00")),
        sa.Column("app_paid_purchase_total", sa.Numeric(14, 2), nullable=False, server_default=sa.text("0.00")),
        sa.Column("referral_discount_base_total", sa.Numeric(14, 2), nullable=False, server_default=sa.text("0.00")),
        sa.Column("current_month_purchase_total", sa.Numeric(14, 2), nullable=False, server_default=sa.text("0.00")),
        sa.Column("previous_month_purchase_total", sa.Numeric(14, 2), nullable=False, server_default=sa.text("0.00")),
        sa.Column("current_discount_percent", sa.Numeric(7, 2), nullable=False, server_default=sa.text("0.00")),
        sa.Column("referrer_promo_code", sa.String(length=120), nullable=True),
        sa.Column("referrer_user_id", sa.BigInteger(), nullable=True),
        sa.Column("referrer_attached_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("promo_changed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("own_promo_code", sa.String(length=120), nullable=True),
        sa.Column("own_promo_issued_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("website_seed_payload", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("website_seeded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["referrer_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["website_identity_id"], ["website_identities.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("own_promo_code"),
        sa.UniqueConstraint("user_id"),
    )
    op.create_index(op.f("ix_referral_profiles_id"), "referral_profiles", ["id"], unique=False)
    op.create_index(op.f("ix_referral_profiles_referrer_promo_code"), "referral_profiles", ["referrer_promo_code"], unique=False)
    op.create_index(op.f("ix_referral_profiles_referrer_user_id"), "referral_profiles", ["referrer_user_id"], unique=False)
    op.create_index(op.f("ix_referral_profiles_user_id"), "referral_profiles", ["user_id"], unique=False)
    op.create_index(op.f("ix_referral_profiles_website_identity_id"), "referral_profiles", ["website_identity_id"], unique=False)

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
    op.create_index(op.f("ix_referral_promo_codes_code"), "referral_promo_codes", ["code"], unique=False)
    op.create_index(op.f("ix_referral_promo_codes_id"), "referral_promo_codes", ["id"], unique=False)
    op.create_index(op.f("ix_referral_promo_codes_is_active"), "referral_promo_codes", ["is_active"], unique=False)
    op.create_index(op.f("ix_referral_promo_codes_owner_user_id"), "referral_promo_codes", ["owner_user_id"], unique=False)

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
    op.create_index(op.f("ix_referral_relationships_id"), "referral_relationships", ["id"], unique=False)
    op.create_index(op.f("ix_referral_relationships_is_active"), "referral_relationships", ["is_active"], unique=False)
    op.create_index(op.f("ix_referral_relationships_referral_promo_code_id"), "referral_relationships", ["referral_promo_code_id"], unique=False)
    op.create_index(op.f("ix_referral_relationships_referred_user_id"), "referral_relationships", ["referred_user_id"], unique=False)
    op.create_index(op.f("ix_referral_relationships_referrer_promo_code"), "referral_relationships", ["referrer_promo_code"], unique=False)
    op.create_index(op.f("ix_referral_relationships_referrer_user_id"), "referral_relationships", ["referrer_user_id"], unique=False)

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
    op.create_index(op.f("ix_referral_commission_entries_buyer_user_id"), "referral_commission_entries", ["buyer_user_id"], unique=False)
    op.create_index(op.f("ix_referral_commission_entries_id"), "referral_commission_entries", ["id"], unique=False)
    op.create_index(op.f("ix_referral_commission_entries_order_id"), "referral_commission_entries", ["order_id"], unique=False)
    op.create_index(op.f("ix_referral_commission_entries_period_end"), "referral_commission_entries", ["period_end"], unique=False)
    op.create_index(op.f("ix_referral_commission_entries_period_start"), "referral_commission_entries", ["period_start"], unique=False)
    op.create_index(op.f("ix_referral_commission_entries_promo_code"), "referral_commission_entries", ["promo_code"], unique=False)
    op.create_index(op.f("ix_referral_commission_entries_referral_relationship_id"), "referral_commission_entries", ["referral_relationship_id"], unique=False)
    op.create_index(op.f("ix_referral_commission_entries_referrer_user_id"), "referral_commission_entries", ["referrer_user_id"], unique=False)
    op.create_index(op.f("ix_referral_commission_entries_status"), "referral_commission_entries", ["status"], unique=False)

    op.add_column("order_benefit_applications", sa.Column("referral_profile_id", sa.BigInteger(), nullable=True))
    op.add_column("order_benefit_applications", sa.Column("referral_promo_code_id", sa.BigInteger(), nullable=True))
    op.add_column("order_benefit_applications", sa.Column("referral_relationship_id", sa.BigInteger(), nullable=True))
    op.add_column("order_benefit_applications", sa.Column("calculation_snapshot", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")))
    op.create_index(op.f("ix_order_benefit_applications_referral_profile_id"), "order_benefit_applications", ["referral_profile_id"], unique=False)
    op.create_index(op.f("ix_order_benefit_applications_referral_promo_code_id"), "order_benefit_applications", ["referral_promo_code_id"], unique=False)
    op.create_index(op.f("ix_order_benefit_applications_referral_relationship_id"), "order_benefit_applications", ["referral_relationship_id"], unique=False)
    op.create_foreign_key(
        "fk_order_benefit_applications_referral_profile_id",
        "order_benefit_applications",
        "referral_profiles",
        ["referral_profile_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_order_benefit_applications_referral_promo_code_id",
        "order_benefit_applications",
        "referral_promo_codes",
        ["referral_promo_code_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_order_benefit_applications_referral_relationship_id",
        "order_benefit_applications",
        "referral_relationships",
        ["referral_relationship_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.add_column("business_ledger_entries", sa.Column("referral_commission_entry_id", sa.BigInteger(), nullable=True))
    op.create_index(op.f("ix_business_ledger_entries_referral_commission_entry_id"), "business_ledger_entries", ["referral_commission_entry_id"], unique=False)
    op.create_foreign_key(
        "fk_business_ledger_entries_referral_commission_entry_id",
        "business_ledger_entries",
        "referral_commission_entries",
        ["referral_commission_entry_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_business_ledger_entries_referral_commission_entry_id", "business_ledger_entries", type_="foreignkey")
    op.drop_index(op.f("ix_business_ledger_entries_referral_commission_entry_id"), table_name="business_ledger_entries")
    op.drop_column("business_ledger_entries", "referral_commission_entry_id")

    op.drop_constraint("fk_order_benefit_applications_referral_relationship_id", "order_benefit_applications", type_="foreignkey")
    op.drop_constraint("fk_order_benefit_applications_referral_promo_code_id", "order_benefit_applications", type_="foreignkey")
    op.drop_constraint("fk_order_benefit_applications_referral_profile_id", "order_benefit_applications", type_="foreignkey")
    op.drop_index(op.f("ix_order_benefit_applications_referral_relationship_id"), table_name="order_benefit_applications")
    op.drop_index(op.f("ix_order_benefit_applications_referral_promo_code_id"), table_name="order_benefit_applications")
    op.drop_index(op.f("ix_order_benefit_applications_referral_profile_id"), table_name="order_benefit_applications")
    op.drop_column("order_benefit_applications", "calculation_snapshot")
    op.drop_column("order_benefit_applications", "referral_relationship_id")
    op.drop_column("order_benefit_applications", "referral_promo_code_id")
    op.drop_column("order_benefit_applications", "referral_profile_id")

    op.drop_index(op.f("ix_referral_commission_entries_status"), table_name="referral_commission_entries")
    op.drop_index(op.f("ix_referral_commission_entries_referrer_user_id"), table_name="referral_commission_entries")
    op.drop_index(op.f("ix_referral_commission_entries_referral_relationship_id"), table_name="referral_commission_entries")
    op.drop_index(op.f("ix_referral_commission_entries_promo_code"), table_name="referral_commission_entries")
    op.drop_index(op.f("ix_referral_commission_entries_period_start"), table_name="referral_commission_entries")
    op.drop_index(op.f("ix_referral_commission_entries_period_end"), table_name="referral_commission_entries")
    op.drop_index(op.f("ix_referral_commission_entries_order_id"), table_name="referral_commission_entries")
    op.drop_index(op.f("ix_referral_commission_entries_id"), table_name="referral_commission_entries")
    op.drop_index(op.f("ix_referral_commission_entries_buyer_user_id"), table_name="referral_commission_entries")
    op.drop_table("referral_commission_entries")

    op.drop_index(op.f("ix_referral_relationships_referrer_user_id"), table_name="referral_relationships")
    op.drop_index(op.f("ix_referral_relationships_referrer_promo_code"), table_name="referral_relationships")
    op.drop_index(op.f("ix_referral_relationships_referred_user_id"), table_name="referral_relationships")
    op.drop_index(op.f("ix_referral_relationships_referral_promo_code_id"), table_name="referral_relationships")
    op.drop_index(op.f("ix_referral_relationships_is_active"), table_name="referral_relationships")
    op.drop_index(op.f("ix_referral_relationships_id"), table_name="referral_relationships")
    op.drop_table("referral_relationships")

    op.drop_index(op.f("ix_referral_promo_codes_owner_user_id"), table_name="referral_promo_codes")
    op.drop_index(op.f("ix_referral_promo_codes_is_active"), table_name="referral_promo_codes")
    op.drop_index(op.f("ix_referral_promo_codes_id"), table_name="referral_promo_codes")
    op.drop_index(op.f("ix_referral_promo_codes_code"), table_name="referral_promo_codes")
    op.drop_table("referral_promo_codes")

    op.drop_index(op.f("ix_referral_profiles_website_identity_id"), table_name="referral_profiles")
    op.drop_index(op.f("ix_referral_profiles_user_id"), table_name="referral_profiles")
    op.drop_index(op.f("ix_referral_profiles_referrer_user_id"), table_name="referral_profiles")
    op.drop_index(op.f("ix_referral_profiles_referrer_promo_code"), table_name="referral_profiles")
    op.drop_index(op.f("ix_referral_profiles_id"), table_name="referral_profiles")
    op.drop_table("referral_profiles")
