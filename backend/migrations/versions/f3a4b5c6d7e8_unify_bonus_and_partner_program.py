"""unify the personal discount and partner program

Revision ID: f3a4b5c6d7e8
Revises: e2f3a4b5c6d7
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "f3a4b5c6d7e8"
down_revision: str | Sequence[str] | None = "e2f3a4b5c6d7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "referral_profiles",
        sa.Column(
            "bitrix_sync_status",
            sa.String(length=32),
            server_default=sa.text("'pending'"),
            nullable=False,
        ),
    )
    op.add_column(
        "referral_profiles",
        sa.Column("bitrix_synced_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "referral_profiles",
        sa.Column("bitrix_sync_error", sa.String(length=500), nullable=True),
    )
    op.add_column(
        "referral_profiles",
        sa.Column("partner_unlocked_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_referral_profiles_bitrix_sync_status",
        "referral_profiles",
        ["bitrix_sync_status"],
        unique=False,
    )
    op.create_index(
        "ix_referral_profiles_partner_unlocked_at",
        "referral_profiles",
        ["partner_unlocked_at"],
        unique=False,
    )
    op.execute(
        """
        UPDATE referral_profiles AS profile
        SET reward_program = 'combined',
            reward_program_selected_at = COALESCE(
                profile.reward_program_selected_at,
                now()
            ),
            reward_program_selection_source = 'system_unified',
            referral_discount_base_total = CASE
                WHEN NULLIF(BTRIM(app_user.promo_code), '') IS NULL THEN 0
                ELSE profile.referral_discount_base_total
            END,
            current_discount_percent = CASE
                WHEN NULLIF(BTRIM(app_user.promo_code), '') IS NULL THEN 0
                ELSE profile.current_discount_percent
            END,
            partner_unlocked_at = CASE
                WHEN NULLIF(BTRIM(app_user.promo_code), '') IS NOT NULL
                    AND profile.referral_discount_base_total >= 100000
                    THEN COALESCE(profile.partner_unlocked_at, now())
                ELSE profile.partner_unlocked_at
            END
        FROM users AS app_user
        WHERE app_user.id = profile.user_id
        """
    )


def downgrade() -> None:
    op.execute(
        """
        UPDATE referral_profiles
        SET reward_program = NULL,
            reward_program_selected_at = NULL,
            reward_program_selection_source = NULL
        WHERE reward_program = 'combined'
        """
    )
    op.drop_index(
        "ix_referral_profiles_partner_unlocked_at",
        table_name="referral_profiles",
    )
    op.drop_index(
        "ix_referral_profiles_bitrix_sync_status",
        table_name="referral_profiles",
    )
    op.drop_column("referral_profiles", "partner_unlocked_at")
    op.drop_column("referral_profiles", "bitrix_sync_error")
    op.drop_column("referral_profiles", "bitrix_synced_at")
    op.drop_column("referral_profiles", "bitrix_sync_status")
