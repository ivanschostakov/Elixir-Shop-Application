"""add username to app users

Revision ID: c8d9e0f1a2b3
Revises: b5c6d7e8f9a0
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "c8d9e0f1a2b3"
down_revision: str | Sequence[str] | None = "b5c6d7e8f9a0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("users", sa.Column("username", sa.String(length=120), nullable=True))
    op.execute(
        sa.text(
            """
            UPDATE users
            SET username = email
            WHERE username IS NULL
              AND email IS NOT NULL
            """
        )
    )
    op.create_index(
        "uq_users_username_lower",
        "users",
        [sa.text("lower(username)")],
        unique=True,
        postgresql_where=sa.text("username IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_users_username_lower", table_name="users")
    op.drop_column("users", "username")
