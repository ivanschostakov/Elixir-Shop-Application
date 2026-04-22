"""make order_draft delivery optional

Revision ID: f6a3c2d1b4e5
Revises: c2b7d97c1f4a
Create Date: 2026-04-22 14:30:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "f6a3c2d1b4e5"
down_revision: Union[str, None] = "c2b7d97c1f4a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "order_drafts",
        "delivery_address_id",
        existing_type=sa.BigInteger(),
        nullable=True,
    )


def downgrade() -> None:
    op.alter_column(
        "order_drafts",
        "delivery_address_id",
        existing_type=sa.BigInteger(),
        nullable=False,
    )
