"""credit approved partner rewards to the MoySklad bonus wallet

Revision ID: a4b5c6d7e8f9
Revises: f3a4b5c6d7e8
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "a4b5c6d7e8f9"
down_revision: str | Sequence[str] | None = "f3a4b5c6d7e8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "app_referral_accruals",
        sa.Column(
            "wallet_sync_status",
            sa.String(length=32),
            server_default=sa.text("'pending'"),
            nullable=False,
        ),
    )
    op.add_column(
        "app_referral_accruals",
        sa.Column("moysklad_counterparty_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "app_referral_accruals",
        sa.Column("moysklad_bonus_program_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "app_referral_accruals",
        sa.Column("moysklad_bonus_transaction_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "app_referral_accruals",
        sa.Column("bonus_points_credited", sa.Integer(), nullable=True),
    )
    op.add_column(
        "app_referral_accruals",
        sa.Column("bonus_rubles_credited", sa.Numeric(14, 2), nullable=True),
    )
    op.add_column(
        "app_referral_accruals",
        sa.Column("wallet_synced_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "app_referral_accruals",
        sa.Column("wallet_sync_error", sa.String(length=500), nullable=True),
    )
    op.add_column(
        "app_referral_accruals",
        sa.Column("wallet_reversal_transaction_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "app_referral_accruals",
        sa.Column("wallet_reversed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_app_referral_accruals_wallet_sync_status",
        "app_referral_accruals",
        ["wallet_sync_status"],
        unique=False,
    )
    op.create_index(
        "ix_app_referral_accruals_moysklad_counterparty_id",
        "app_referral_accruals",
        ["moysklad_counterparty_id"],
        unique=False,
    )
    op.create_unique_constraint(
        "uq_app_referral_accruals_moysklad_bonus_transaction_id",
        "app_referral_accruals",
        ["moysklad_bonus_transaction_id"],
    )
    op.create_unique_constraint(
        "uq_app_referral_accruals_wallet_reversal_transaction_id",
        "app_referral_accruals",
        ["wallet_reversal_transaction_id"],
    )
    op.execute(
        """
        UPDATE app_referral_accruals
        SET wallet_sync_status = 'not_applicable'
        WHERE status = 'rejected'
        """
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_app_referral_accruals_wallet_reversal_transaction_id",
        "app_referral_accruals",
        type_="unique",
    )
    op.drop_constraint(
        "uq_app_referral_accruals_moysklad_bonus_transaction_id",
        "app_referral_accruals",
        type_="unique",
    )
    op.drop_index(
        "ix_app_referral_accruals_moysklad_counterparty_id",
        table_name="app_referral_accruals",
    )
    op.drop_index(
        "ix_app_referral_accruals_wallet_sync_status",
        table_name="app_referral_accruals",
    )
    op.drop_column("app_referral_accruals", "wallet_reversed_at")
    op.drop_column("app_referral_accruals", "wallet_reversal_transaction_id")
    op.drop_column("app_referral_accruals", "wallet_sync_error")
    op.drop_column("app_referral_accruals", "wallet_synced_at")
    op.drop_column("app_referral_accruals", "bonus_rubles_credited")
    op.drop_column("app_referral_accruals", "bonus_points_credited")
    op.drop_column("app_referral_accruals", "moysklad_bonus_transaction_id")
    op.drop_column("app_referral_accruals", "moysklad_bonus_program_id")
    op.drop_column("app_referral_accruals", "moysklad_counterparty_id")
    op.drop_column("app_referral_accruals", "wallet_sync_status")
