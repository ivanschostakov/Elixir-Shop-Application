"""harden admin integration runs

Revision ID: a1b2c3d4e5f6
Revises: f7a8b9c0d1e2
Create Date: 2026-07-22 18:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "a1b2c3d4e5f6"
down_revision = "f7a8b9c0d1e2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("integration_runs", sa.Column("target_type", sa.String(length=60), nullable=True))
    op.add_column("integration_runs", sa.Column("target_id", sa.String(length=160), nullable=True))
    op.add_column("integration_runs", sa.Column("retry_of_id", sa.BigInteger(), nullable=True))
    op.add_column("integration_runs", sa.Column("max_attempts", sa.Integer(), server_default=sa.text("3"), nullable=False))
    op.add_column("integration_runs", sa.Column("heartbeat_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("integration_runs", sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=True))
    op.alter_column("integration_runs", "attempts", existing_type=sa.Integer(), server_default=sa.text("0"), existing_nullable=False)
    op.create_foreign_key("fk_integration_runs_retry_of", "integration_runs", "integration_runs", ["retry_of_id"], ["id"], ondelete="SET NULL")
    op.create_index("ix_integration_runs_target_type", "integration_runs", ["target_type"])
    op.create_index("ix_integration_runs_target_id", "integration_runs", ["target_id"])
    op.create_index("ix_integration_runs_retry_of_id", "integration_runs", ["retry_of_id"])
    op.create_index("ix_integration_runs_heartbeat_at", "integration_runs", ["heartbeat_at"])
    op.create_index("ix_integration_runs_next_attempt_at", "integration_runs", ["next_attempt_at"])
    op.create_index("ix_integration_runs_target", "integration_runs", ["target_type", "target_id", "started_at"])
    op.execute(
        "UPDATE admin_roles SET permissions = permissions || '[\"orders.recover\"]'::jsonb "
        "WHERE code IN ('sales', 'logistics') AND NOT permissions ? 'orders.recover'"
    )


def downgrade() -> None:
    op.execute("UPDATE admin_roles SET permissions = permissions - 'orders.recover' WHERE code IN ('sales', 'logistics')")
    op.drop_index("ix_integration_runs_target", table_name="integration_runs")
    op.drop_index("ix_integration_runs_next_attempt_at", table_name="integration_runs")
    op.drop_index("ix_integration_runs_heartbeat_at", table_name="integration_runs")
    op.drop_index("ix_integration_runs_retry_of_id", table_name="integration_runs")
    op.drop_index("ix_integration_runs_target_id", table_name="integration_runs")
    op.drop_index("ix_integration_runs_target_type", table_name="integration_runs")
    op.drop_constraint("fk_integration_runs_retry_of", "integration_runs", type_="foreignkey")
    op.alter_column("integration_runs", "attempts", existing_type=sa.Integer(), server_default=sa.text("1"), existing_nullable=False)
    op.drop_column("integration_runs", "next_attempt_at")
    op.drop_column("integration_runs", "heartbeat_at")
    op.drop_column("integration_runs", "max_attempts")
    op.drop_column("integration_runs", "retry_of_id")
    op.drop_column("integration_runs", "target_id")
    op.drop_column("integration_runs", "target_type")
