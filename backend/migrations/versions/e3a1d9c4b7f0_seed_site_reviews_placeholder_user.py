"""seed site reviews placeholder user

Revision ID: e3a1d9c4b7f0
Revises: b9e3f4a1d2c7
Create Date: 2026-05-01 13:55:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "e3a1d9c4b7f0"
down_revision: Union[str, Sequence[str], None] = "b9e3f4a1d2c7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

PLACEHOLDER_USER_ID = 0


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table("users"):
        return

    existing = bind.execute(
        sa.text("SELECT id FROM users WHERE id = :user_id"),
        {"user_id": PLACEHOLDER_USER_ID},
    ).scalar_one_or_none()
    if existing is not None:
        return

    bind.execute(
        sa.text(
            """
            INSERT INTO users (
                id,
                username,
                email,
                password_hash,
                name,
                surname,
                is_active,
                last_active_at,
                is_verified,
                phone_number,
                created_at,
                updated_at
            )
            VALUES (
                :id,
                :username,
                :email,
                :password_hash,
                :name,
                :surname,
                :is_active,
                NULL,
                :is_verified,
                NULL,
                NOW(),
                NOW()
            )
            """
        ),
        {
            "id": PLACEHOLDER_USER_ID,
            "username": "site_reviews",
            "email": "site-reviews+placeholder@elixir.local",
            "password_hash": "$scrypt$ln=16,r=8,p=1$MGYMoZRS6p0zBuDc29t7Tw$n0CnaymUUEGDuVcM678IqXJ1yZpsJiQ6+WUZ7TJMEYk",
            "name": "С сайта",
            "surname": "С сайта",
            "is_active": False,
            "is_verified": True,
        },
    )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table("users"):
        return

    bind.execute(
        sa.text("DELETE FROM users WHERE id = :user_id"),
        {"user_id": PLACEHOLDER_USER_ID},
    )
