"""add current_path to user push tokens

Revision ID: b9e3f4a1d2c7
Revises: a0f1c2d3e4b5
Create Date: 2026-05-01 12:20:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "b9e3f4a1d2c7"
down_revision: Union[str, Sequence[str], None] = "a0f1c2d3e4b5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("user_push_tokens", sa.Column("current_path", sa.String(length=512), nullable=True))


def downgrade() -> None:
    op.drop_column("user_push_tokens", "current_path")
