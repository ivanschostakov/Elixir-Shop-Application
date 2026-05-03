"""add webhook dedupe and notification unique constraints

Revision ID: f1a2b3c4d5e6
Revises: c9d4a2b7e6f1
Create Date: 2026-05-03 08:30:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "f1a2b3c4d5e6"
down_revision: Union[str, Sequence[str], None] = "c9d4a2b7e6f1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "webhook_deliveries",
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column("delivery_id", sa.String(length=255), nullable=True),
        sa.Column("signature_hash", sa.String(length=64), nullable=True),
        sa.Column("signature_timestamp", sa.String(length=128), nullable=True),
        sa.Column("payload_hash", sa.String(length=64), nullable=True),
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "(delivery_id IS NOT NULL) OR "
            "(signature_hash IS NOT NULL AND signature_timestamp IS NOT NULL) OR "
            "(payload_hash IS NOT NULL)",
            name="ck_webhook_deliveries_has_dedupe_key",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("provider", "delivery_id", name="uq_webhook_deliveries_provider_delivery_id"),
        sa.UniqueConstraint(
            "provider",
            "signature_hash",
            "signature_timestamp",
            name="uq_webhook_deliveries_provider_signature_ts",
        ),
    )
    op.create_index(op.f("ix_webhook_deliveries_id"), "webhook_deliveries", ["id"], unique=False)
    op.create_index(op.f("ix_webhook_deliveries_provider"), "webhook_deliveries", ["provider"], unique=False)
    op.create_index("ix_webhook_deliveries_provider_created_at", "webhook_deliveries", ["provider", "created_at"], unique=False)

    op.execute(
        """
        DELETE FROM notification_dispatches AS newer
        USING notification_dispatches AS older
        WHERE newer.id > older.id
          AND newer.user_id = older.user_id
          AND newer.type = older.type
          AND newer.dedupe_key = older.dedupe_key
          AND newer.sent_at = older.sent_at
        """
    )
    op.create_unique_constraint(
        "uq_notification_dispatches_user_type_dedupe_sent_at",
        "notification_dispatches",
        ["user_id", "type", "dedupe_key", "sent_at"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_notification_dispatches_user_type_dedupe_sent_at",
        "notification_dispatches",
        type_="unique",
    )

    op.drop_index("ix_webhook_deliveries_provider_created_at", table_name="webhook_deliveries")
    op.drop_index(op.f("ix_webhook_deliveries_provider"), table_name="webhook_deliveries")
    op.drop_index(op.f("ix_webhook_deliveries_id"), table_name="webhook_deliveries")
    op.drop_table("webhook_deliveries")
