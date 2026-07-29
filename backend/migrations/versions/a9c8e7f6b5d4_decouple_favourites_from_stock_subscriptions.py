"""decouple favourites from stock subscriptions

Revision ID: a9c8e7f6b5d4
Revises: a1c2e3f4b5d6, d4e5f6a7b8c9, e7f8a9b0c1d2
Create Date: 2026-07-30 03:35:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "a9c8e7f6b5d4"
down_revision = ("a1c2e3f4b5d6", "d4e5f6a7b8c9", "e7f8a9b0c1d2")
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "stock_notification_subscriptions" not in inspector.get_table_names():
        return
    op.execute(
        sa.text(
            """
            UPDATE stock_notification_subscriptions
            SET is_active = false, updated_at = now()
            WHERE is_active = true
            """
        )
    )


def downgrade() -> None:
    pass
