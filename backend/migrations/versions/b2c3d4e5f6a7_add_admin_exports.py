"""add admin exports

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-07-22 20:00:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "b2c3d4e5f6a7"
down_revision = "a1b2c3d4e5f6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "integration_runs",
        sa.Column(
            "input_json",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
    )
    op.execute(
        "UPDATE admin_roles SET permissions = permissions || '[\"exports.read\"]'::jsonb "
        "WHERE code IN ('support', 'content', 'logistics') AND NOT permissions ? 'exports.read'"
    )


def downgrade() -> None:
    op.execute(
        "UPDATE admin_roles SET permissions = permissions - 'exports.read' "
        "WHERE code IN ('support', 'content', 'logistics')"
    )
    op.drop_column("integration_runs", "input_json")
