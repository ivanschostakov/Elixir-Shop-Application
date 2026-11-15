"""Distinguish saved recipients from snapshots of the checkout profile."""

from alembic import op
import sqlalchemy as sa

revision = "e4a6c8e0f2b4"
down_revision = "d3f5a7c9e1b2"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("delivery_recipients", sa.Column("is_profile_snapshot", sa.Boolean(), nullable=True))


def downgrade():
    op.drop_column("delivery_recipients", "is_profile_snapshot")
