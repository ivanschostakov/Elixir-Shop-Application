"""add expiring loyalty bonus credits

Revision ID: e6f7a8b9c0d1
Revises: a4b5c6d7e8f9
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "e6f7a8b9c0d1"
down_revision: str | Sequence[str] | None = "a4b5c6d7e8f9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # The cumulative program is the default. Profiles written by the temporary
    # unified-program release are migrated back to an unconfirmed default so
    # customers at/above 30,000 RUB can make the documented one-time choice.
    op.execute(
        """
        UPDATE referral_profiles
        SET reward_program='bonus',
            reward_program_selected_at=NULL,
            reward_program_selection_source='system_default',
            reward_program_snapshot=COALESCE(reward_program_snapshot, '{}'::jsonb) ||
                '{"migrated_from":"combined"}'::jsonb
        WHERE reward_program='combined'
        """
    )
    op.add_column(
        "users",
        sa.Column("welcome_bonus_granted_at", sa.DateTime(timezone=True), nullable=True),
    )
    # Existing accounts are intentionally marked as processed. Only accounts
    # created after this migration receive the app-install welcome bonus.
    op.execute("UPDATE users SET welcome_bonus_granted_at = now()")

    op.add_column(
        "app_referral_accruals",
        sa.Column(
            "settlement_method",
            sa.String(length=32),
            server_default=sa.text("'deposit'"),
            nullable=False,
        ),
    )
    op.add_column(
        "app_referral_accruals",
        sa.Column("settlement_reference", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "app_referral_accruals",
        sa.Column("settled_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "app_referral_accruals",
        sa.Column("settled_by_admin_user_id", sa.BigInteger(), nullable=True),
    )
    op.create_index(
        "ix_app_referral_accruals_settlement_method",
        "app_referral_accruals",
        ["settlement_method"],
        unique=False,
    )

    op.create_table(
        "loyalty_bonus_credits",
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("order_id", sa.BigInteger(), nullable=True),
        sa.Column("review_id", sa.BigInteger(), nullable=True),
        sa.Column("source_kind", sa.String(length=48), nullable=False),
        sa.Column("idempotency_key", sa.String(length=160), nullable=False),
        sa.Column("points", sa.Integer(), nullable=False),
        sa.Column("spent_points", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("status", sa.String(length=32), server_default=sa.text("'pending'"), nullable=False),
        sa.Column("earned_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("available_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expired_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reversed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("moysklad_bonus_program_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("moysklad_bonus_transaction_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("moysklad_debit_transaction_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("sync_error", sa.String(length=500), nullable=True),
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["order_id"], ["orders.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["review_id"], ["reviews.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("idempotency_key", name="uq_loyalty_bonus_credits_idempotency_key"),
        sa.UniqueConstraint("moysklad_bonus_transaction_id"),
        sa.UniqueConstraint("moysklad_debit_transaction_id"),
    )
    for column in (
        "id",
        "user_id",
        "order_id",
        "review_id",
        "source_kind",
        "status",
        "earned_at",
        "available_at",
        "expires_at",
    ):
        op.create_index(
            f"ix_loyalty_bonus_credits_{column}",
            "loyalty_bonus_credits",
            [column],
            unique=False,
        )

    op.execute(
        sa.text(
            """
            UPDATE admin_marketing_automations
            SET settings_json = COALESCE(settings_json, '{}'::jsonb) || CAST(:settings AS jsonb)
            WHERE code = 'review_reminder'
            """
        ).bindparams(
            settings=(
                '{"after_days":3,'
                '"title":"Оставьте отзыв — получите бонусы",'
                '"body":"Расскажите о покупке: 100 бонусов за текстовый отзыв или 200 бонусов за отзыв с фото."}'
            )
        )
    )


def downgrade() -> None:
    op.execute(
        """
        UPDATE admin_marketing_automations
        SET settings_json = COALESCE(settings_json, '{}'::jsonb) ||
            '{"after_days":30,"title":"Поделитесь отзывом","body":"Прошел месяц после заказа. Оцените препарат и оставьте отзыв."}'::jsonb
        WHERE code = 'review_reminder'
        """
    )
    op.drop_table("loyalty_bonus_credits")
    op.drop_index(
        "ix_app_referral_accruals_settlement_method",
        table_name="app_referral_accruals",
    )
    op.drop_column("app_referral_accruals", "settled_by_admin_user_id")
    op.drop_column("app_referral_accruals", "settled_at")
    op.drop_column("app_referral_accruals", "settlement_reference")
    op.drop_column("app_referral_accruals", "settlement_method")
    op.drop_column("users", "welcome_bonus_granted_at")
    op.execute(
        """
        UPDATE referral_profiles
        SET reward_program='combined',
            reward_program_selected_at=COALESCE(reward_program_selected_at, now()),
            reward_program_selection_source='system_unified'
        WHERE reward_program='bonus' AND reward_program_selection_source='system_default'
        """
    )
