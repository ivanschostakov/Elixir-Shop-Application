"""add recipient fields to order drafts

Revision ID: e4a8f7c1d2b4
Revises: d1f90c6f8b72
Create Date: 2026-04-20 22:58:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "e4a8f7c1d2b4"
down_revision: Union[str, Sequence[str], None] = "d1f90c6f8b72"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("order_drafts", sa.Column("recipient_name", sa.String(length=100), nullable=True))
    op.add_column("order_drafts", sa.Column("recipient_phone", sa.String(length=80), nullable=True))
    op.add_column("order_drafts", sa.Column("recipient_email", sa.String(length=100), nullable=True))


def downgrade() -> None:
    op.drop_column("order_drafts", "recipient_email")
    op.drop_column("order_drafts", "recipient_phone")
    op.drop_column("order_drafts", "recipient_name")
