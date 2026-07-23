"""complete customer segmentation

Revision ID: f2e3d4c5b6a7
Revises: e1f2a3b4c5d6
Create Date: 2026-07-22 23:40:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "f2e3d4c5b6a7"
down_revision: str | Sequence[str] | None = "e1f2a3b4c5d6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _table_exists(inspector: sa.Inspector, table_name: str) -> bool:
    return inspector.has_table(table_name)


def _columns(inspector: sa.Inspector, table_name: str) -> set[str]:
    return {column["name"] for column in inspector.get_columns(table_name)} if inspector.has_table(table_name) else set()


def _add_column_if_missing(table_name: str, column: sa.Column) -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if column.name in _columns(inspector, table_name):
        return
    with op.batch_alter_table(table_name) as batch:
        batch.add_column(column)


def _create_index_if_missing(index_name: str, table_name: str, columns: list[str]) -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if any(index["name"] == index_name for index in inspector.get_indexes(table_name)):
        return
    op.create_index(index_name, table_name, columns)


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if _table_exists(inspector, "admin_customer_segments"):
        _add_column_if_missing("admin_customer_segments", sa.Column("segment_type", sa.String(length=24), nullable=False, server_default=sa.text("'dynamic'")))
        _add_column_if_missing("admin_customer_segments", sa.Column("snapshot_version", sa.Integer(), nullable=False, server_default=sa.text("0")))
        _add_column_if_missing("admin_customer_segments", sa.Column("snapshot_at", sa.DateTime(timezone=True), nullable=True))
        _add_column_if_missing("admin_customer_segments", sa.Column("snapshot_count", sa.Integer(), nullable=False, server_default=sa.text("0")))
        _create_index_if_missing("ix_admin_customer_segments_segment_type", "admin_customer_segments", ["segment_type"])

    if not _table_exists(inspector, "admin_customer_segment_snapshot_items"):
        op.create_table(
            "admin_customer_segment_snapshot_items",
            sa.Column("segment_id", sa.BigInteger(), nullable=False),
            sa.Column("user_id", sa.BigInteger(), nullable=False),
            sa.Column("snapshot_version", sa.Integer(), nullable=False, server_default=sa.text("1")),
            sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.ForeignKeyConstraint(["segment_id"], ["admin_customer_segments.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("segment_id", "user_id", name="uq_admin_customer_segment_snapshot_user"),
        )
        op.create_index("ix_admin_customer_segment_snapshot_items_id", "admin_customer_segment_snapshot_items", ["id"])
        op.create_index("ix_admin_customer_segment_snapshot_items_segment_id", "admin_customer_segment_snapshot_items", ["segment_id"])
        op.create_index("ix_admin_customer_segment_snapshot_items_user_id", "admin_customer_segment_snapshot_items", ["user_id"])
        op.create_index("ix_admin_customer_segment_snapshot_items_snapshot_version", "admin_customer_segment_snapshot_items", ["snapshot_version"])

    if not _table_exists(inspector, "admin_customer_segment_history"):
        op.create_table(
            "admin_customer_segment_history",
            sa.Column("segment_id", sa.BigInteger(), nullable=False),
            sa.Column("actor_user_id", sa.BigInteger(), nullable=True),
            sa.Column("action", sa.String(length=80), nullable=False),
            sa.Column("before_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
            sa.Column("after_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
            sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
            sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.ForeignKeyConstraint(["actor_user_id"], ["admins.user_id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["segment_id"], ["admin_customer_segments.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_admin_customer_segment_history_id", "admin_customer_segment_history", ["id"])
        op.create_index("ix_admin_customer_segment_history_segment_id", "admin_customer_segment_history", ["segment_id"])
        op.create_index("ix_admin_customer_segment_history_actor_user_id", "admin_customer_segment_history", ["actor_user_id"])
        op.create_index("ix_admin_customer_segment_history_action", "admin_customer_segment_history", ["action"])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    for table_name in ("admin_customer_segment_history", "admin_customer_segment_snapshot_items"):
        if _table_exists(inspector, table_name):
            op.drop_table(table_name)
