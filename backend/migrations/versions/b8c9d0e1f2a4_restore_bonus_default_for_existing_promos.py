"""restore the bonus default for profiles with an existing promo

Revision ID: b8c9d0e1f2a4
Revises: a7b8c9d0e1f3
"""

from collections.abc import Sequence

from alembic import op


revision: str = "b8c9d0e1f2a4"
down_revision: str | Sequence[str] | None = "a7b8c9d0e1f3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE referral_profiles AS profile
        SET reward_program='bonus',
            reward_program_selected_at=NULL,
            reward_program_selection_source='system_default',
            reward_program_snapshot=(
                COALESCE(profile.reward_program_snapshot, '{}'::jsonb)
                - 'recovered_existing_promo'
            ) || jsonb_strip_nulls(jsonb_build_object(
                'deferred_existing_promo',
                NULLIF(BTRIM(app_user.promo_code), ''),
                'restored_bonus_default',
                true
            ))
        FROM users AS app_user
        WHERE app_user.id=profile.user_id
          AND profile.reward_program_selection_source='system_existing_promo'
        """
    )


def downgrade() -> None:
    op.execute(
        """
        UPDATE referral_profiles AS profile
        SET reward_program='partner',
            reward_program_selected_at=now(),
            reward_program_selection_source='system_existing_promo',
            reward_program_snapshot=(
                COALESCE(profile.reward_program_snapshot, '{}'::jsonb)
                - 'deferred_existing_promo'
                - 'restored_bonus_default'
            ) || jsonb_strip_nulls(jsonb_build_object(
                'recovered_existing_promo',
                NULLIF(BTRIM(app_user.promo_code), '')
            ))
        FROM users AS app_user
        WHERE app_user.id=profile.user_id
          AND profile.reward_program='bonus'
          AND profile.reward_program_selection_source='system_default'
          AND COALESCE(profile.reward_program_snapshot, '{}'::jsonb)
                @> '{"restored_bonus_default": true}'::jsonb
        """
    )
