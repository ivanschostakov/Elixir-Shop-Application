"""restore the partner program for profiles with an existing promo

Revision ID: a7b8c9d0e1f3
Revises: e6f7a8b9c0d1
"""

from collections.abc import Sequence

from alembic import op


revision: str = "a7b8c9d0e1f3"
down_revision: str | Sequence[str] | None = "e6f7a8b9c0d1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE referral_profiles AS profile
        SET reward_program='partner',
            reward_program_selected_at=COALESCE(
                profile.reward_program_selected_at,
                now()
            ),
            reward_program_selection_source='system_existing_promo',
            reward_program_snapshot=COALESCE(
                profile.reward_program_snapshot,
                '{}'::jsonb
            ) || jsonb_build_object(
                'recovered_existing_promo',
                BTRIM(app_user.promo_code)
            )
        FROM users AS app_user
        WHERE app_user.id=profile.user_id
          AND profile.reward_program='bonus'
          AND profile.reward_program_selection_source='system_default'
          AND NULLIF(BTRIM(app_user.promo_code), '') IS NOT NULL
        """
    )


def downgrade() -> None:
    op.execute(
        """
        UPDATE referral_profiles
        SET reward_program='bonus',
            reward_program_selected_at=NULL,
            reward_program_selection_source='system_default',
            reward_program_snapshot=COALESCE(
                reward_program_snapshot,
                '{}'::jsonb
            ) - 'recovered_existing_promo'
        WHERE reward_program='partner'
          AND reward_program_selection_source='system_existing_promo'
        """
    )
