"""make orders draft_id nullable

Revision ID: c61b7b1f96f3
Revises: 8f7c3b2a1d4e
Create Date: 2026-04-23 12:05:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "c61b7b1f96f3"
down_revision: Union[str, Sequence[str], None] = "8f7c3b2a1d4e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column("orders", "draft_id", existing_type=sa.BigInteger(), nullable=True)


def downgrade() -> None:
    op.execute(sa.text("DELETE FROM orders WHERE draft_id IS NULL"))
    op.alter_column("orders", "draft_id", existing_type=sa.BigInteger(), nullable=False)
