"""normalize legacy successful payment states

Revision ID: f8a9b0c1d2e3
Revises: e7f8a9b0c1d2
"""

from collections.abc import Sequence

from alembic import op


revision: str = "f8a9b0c1d2e3"
down_revision: str | Sequence[str] | None = "e7f8a9b0c1d2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE orders
        SET
            payment_status = 'paid',
            is_paid = true,
            payment_paid_at = COALESCE(payment_paid_at, updated_at, created_at),
            payment_error = ''
        WHERE lower(trim(COALESCE(payment_status, ''))) IN ('ok', 'success')
          AND lower(trim(COALESCE(payment_method, ''))) = 'sbp'
        """
    )


def downgrade() -> None:
    # The legacy provider value cannot be reconstructed reliably.
    pass
