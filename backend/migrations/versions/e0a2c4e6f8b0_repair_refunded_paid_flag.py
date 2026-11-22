"""Repair the contradictory paid flag left by previously failed CRM callbacks."""
from alembic import op

revision = "e0a2c4e6f8b0"
down_revision = "d9f1a3b5c7e9"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("UPDATE orders SET is_paid = false WHERE payment_status = 'refunded' AND is_paid = true")


def downgrade():
    # Restoring contradictory financial data is never part of a schema rollback.
    pass
