"""Do not overwrite a new reservation with a snapshot fetched before it."""
from alembic import op
import sqlalchemy as sa

revision = "d9f1a3b5c7e9"
down_revision = "c8e0a2b4d6f8"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("variants", sa.Column("stock_valid_after", sa.DateTime(timezone=True)))


def downgrade():
    op.drop_column("variants", "stock_valid_after")
