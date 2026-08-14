"""activate the base promo discount in the cashback program

Revision ID: d0e1f2a3b4c6
Revises: c9d0e1f2a3b5
"""

from collections.abc import Sequence

from alembic import op


revision: str = "d0e1f2a3b4c6"
down_revision: str | Sequence[str] | None = "c9d0e1f2a3b5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE referral_profiles AS profile
        SET current_discount_percent=CASE
                WHEN NULLIF(BTRIM(app_user.promo_code), '') IS NULL THEN 0
                ELSE 3
            END,
            reward_program_snapshot=(
                COALESCE(profile.reward_program_snapshot, '{}'::jsonb)
                - 'deferred_existing_promo'
            ) || jsonb_strip_nulls(jsonb_build_object(
                'active_base_promo', NULLIF(BTRIM(app_user.promo_code), '')
            ))
        FROM users AS app_user
        WHERE app_user.id=profile.user_id
          AND profile.reward_program='bonus'
        """
    )


def downgrade() -> None:
    op.execute(
        """
        UPDATE referral_profiles
        SET current_discount_percent=0,
            reward_program_snapshot=COALESCE(reward_program_snapshot, '{}'::jsonb)
                - 'active_base_promo'
        WHERE reward_program='bonus'
        """
    )
