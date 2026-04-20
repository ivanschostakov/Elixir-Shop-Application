"""backfill missing baskets

Revision ID: 8b3a859f5ff7
Revises: 3a5e62ea7c88
Create Date: 2026-04-08 11:25:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "8b3a859f5ff7"
down_revision: Union[str, Sequence[str], None] = "3a5e62ea7c88"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


USERS_TABLE = "users"
BASKETS_TABLE = "baskets"


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not inspector.has_table(USERS_TABLE) or not inspector.has_table(BASKETS_TABLE):
        return

    bind.execute(
        sa.text(
            f"""
            INSERT INTO {BASKETS_TABLE} (user_id, created_at, updated_at)
            SELECT users.id, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
            FROM {USERS_TABLE} AS users
            LEFT JOIN {BASKETS_TABLE} AS baskets ON baskets.user_id = users.id
            WHERE baskets.user_id IS NULL
            """
        )
    )


def downgrade() -> None:
    # This is a one-time data backfill; downgrading should keep created baskets intact.
    return
