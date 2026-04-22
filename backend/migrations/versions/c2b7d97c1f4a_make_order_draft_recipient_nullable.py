"""make order_drafts.recipient_id nullable

Revision ID: c2b7d97c1f4a
Revises: b8c2a41f6d90
Create Date: 2026-04-21 10:30:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "c2b7d97c1f4a"
down_revision: Union[str, Sequence[str], None] = "b8c2a41f6d90"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "order_drafts",
        "recipient_id",
        existing_type=sa.BigInteger(),
        nullable=True,
    )


def downgrade() -> None:
    bind = op.get_bind()
    bind.execute(
        sa.text(
            """
            WITH missing_users AS (
                SELECT DISTINCT user_id
                FROM order_drafts
                WHERE recipient_id IS NULL
            ),
            created_recipients AS (
                INSERT INTO delivery_recipients (
                    user_id,
                    name,
                    surname,
                    phone,
                    email,
                    created_at,
                    updated_at
                )
                SELECT
                    users.id,
                    COALESCE(NULLIF(TRIM(users.name), ''), 'Покупатель'),
                    COALESCE(NULLIF(TRIM(users.surname), ''), 'Получатель'),
                    COALESCE(users.phone_number, ''),
                    COALESCE(users.email, ''),
                    CURRENT_TIMESTAMP,
                    CURRENT_TIMESTAMP
                FROM users
                JOIN missing_users ON missing_users.user_id = users.id
                RETURNING id, user_id
            )
            UPDATE order_drafts
            SET recipient_id = created_recipients.id
            FROM created_recipients
            WHERE
                order_drafts.user_id = created_recipients.user_id
                AND order_drafts.recipient_id IS NULL
            """
        )
    )

    op.alter_column(
        "order_drafts",
        "recipient_id",
        existing_type=sa.BigInteger(),
        nullable=False,
    )
