"""add name and comment to order drafts

Revision ID: d1f90c6f8b72
Revises: bd9a1c9f7d21
Create Date: 2026-04-20 22:15:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "d1f90c6f8b72"
down_revision: Union[str, Sequence[str], None] = "bd9a1c9f7d21"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("order_drafts", sa.Column("draft_name", sa.String(length=100), nullable=True))
    op.add_column("order_drafts", sa.Column("comment", sa.String(length=500), nullable=True))


def downgrade() -> None:
    op.drop_column("order_drafts", "comment")
    op.drop_column("order_drafts", "draft_name")
