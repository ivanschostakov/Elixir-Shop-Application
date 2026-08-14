"""zero dormant referral discounts for the bonus program

Revision ID: c9d0e1f2a3b5
Revises: b8c9d0e1f2a4
"""

from collections.abc import Sequence

from alembic import op


revision: str = "c9d0e1f2a3b5"
down_revision: str | Sequence[str] | None = "b8c9d0e1f2a4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE referral_profiles
        SET current_discount_percent=0
        WHERE reward_program='bonus'
          AND current_discount_percent<>0
        """
    )


def downgrade() -> None:
    # The previous cached discount cannot be reconstructed safely. It will be
    # recalculated if the customer explicitly selects the partner program.
    pass
