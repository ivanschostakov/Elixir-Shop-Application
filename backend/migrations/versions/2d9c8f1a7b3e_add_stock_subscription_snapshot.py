"""add stock subscription snapshot

Revision ID: 2d9c8f1a7b3e
Revises: 6b9e2a4c1d7f
Create Date: 2026-05-01 04:25:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "2d9c8f1a7b3e"
down_revision: Union[str, Sequence[str], None] = "6b9e2a4c1d7f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "stock_notification_subscriptions",
        sa.Column("last_seen_stock", sa.Integer(), server_default=sa.text("0"), nullable=False),
    )


def downgrade() -> None:
    op.drop_column("stock_notification_subscriptions", "last_seen_stock")
