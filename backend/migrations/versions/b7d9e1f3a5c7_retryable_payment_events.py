"""Retry verified payment events without losing financial transitions."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
revision = "b7d9e1f3a5c7"
down_revision = "a6c8e0f2b4d7"
branch_labels = None
depends_on = None

def upgrade():
    op.add_column("webhook_deliveries", sa.Column("status", sa.String(24), server_default="processed", nullable=False))
    op.add_column("webhook_deliveries", sa.Column("payload_json", JSONB))
    op.add_column("webhook_deliveries", sa.Column("attempts", sa.Integer, server_default="0", nullable=False))
    op.add_column("webhook_deliveries", sa.Column("lease_until", sa.DateTime(timezone=True)))
    op.add_column("webhook_deliveries", sa.Column("next_attempt_at", sa.DateTime(timezone=True)))
    op.add_column("webhook_deliveries", sa.Column("last_error", sa.String(1000)))
    op.create_index("ix_webhook_deliveries_status", "webhook_deliveries", ["status"])
    op.create_index("ix_webhook_deliveries_next_attempt_at", "webhook_deliveries", ["next_attempt_at"])

def downgrade():
    op.drop_index("ix_webhook_deliveries_next_attempt_at")
    op.drop_index("ix_webhook_deliveries_status")
    for c in ["last_error", "next_attempt_at", "lease_until", "attempts", "payload_json", "status"]:op.drop_column("webhook_deliveries", c)
