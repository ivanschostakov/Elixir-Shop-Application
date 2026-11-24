"""Store actionable mentor notification context and the first acknowledged response."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "ab31dc71e920"
down_revision = "e0a2c4e6f8b0"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("ai_companion_reminders", sa.Column("context", sa.JSON().with_variant(postgresql.JSONB(), "postgresql"), nullable=True))


def downgrade():
    op.drop_column("ai_companion_reminders", "context")
