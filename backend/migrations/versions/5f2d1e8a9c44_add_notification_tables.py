"""add notification tables

Revision ID: 5f2d1e8a9c44
Revises: 27d03a60b2ea
Create Date: 2026-05-01 02:40:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "5f2d1e8a9c44"
down_revision: Union[str, Sequence[str], None] = "27d03a60b2ea"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "notification_dispatches",
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("type", sa.String(length=64), nullable=False),
        sa.Column("dedupe_key", sa.String(length=255), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("payload_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_notification_dispatches_id"), "notification_dispatches", ["id"], unique=False)
    op.create_index(op.f("ix_notification_dispatches_user_id"), "notification_dispatches", ["user_id"], unique=False)
    op.create_index(op.f("ix_notification_dispatches_type"), "notification_dispatches", ["type"], unique=False)
    op.create_index(op.f("ix_notification_dispatches_sent_at"), "notification_dispatches", ["sent_at"], unique=False)
    op.create_index(
        "ix_notification_dispatches_user_type_sent_at",
        "notification_dispatches",
        ["user_id", "type", "sent_at"],
        unique=False,
    )
    op.create_index(
        "ix_notification_dispatches_type_dedupe_key",
        "notification_dispatches",
        ["type", "dedupe_key"],
        unique=False,
    )

    op.create_table(
        "stock_notification_subscriptions",
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("variant_id", sa.BigInteger(), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("notified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["variant_id"], ["doses.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "variant_id", name="uq_stock_notification_subscriptions_user_variant"),
    )
    op.create_index(
        op.f("ix_stock_notification_subscriptions_id"),
        "stock_notification_subscriptions",
        ["id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_stock_notification_subscriptions_user_id"),
        "stock_notification_subscriptions",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_stock_notification_subscriptions_variant_id"),
        "stock_notification_subscriptions",
        ["variant_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_stock_notification_subscriptions_variant_id"), table_name="stock_notification_subscriptions")
    op.drop_index(op.f("ix_stock_notification_subscriptions_user_id"), table_name="stock_notification_subscriptions")
    op.drop_index(op.f("ix_stock_notification_subscriptions_id"), table_name="stock_notification_subscriptions")
    op.drop_table("stock_notification_subscriptions")

    op.drop_index("ix_notification_dispatches_type_dedupe_key", table_name="notification_dispatches")
    op.drop_index("ix_notification_dispatches_user_type_sent_at", table_name="notification_dispatches")
    op.drop_index(op.f("ix_notification_dispatches_sent_at"), table_name="notification_dispatches")
    op.drop_index(op.f("ix_notification_dispatches_type"), table_name="notification_dispatches")
    op.drop_index(op.f("ix_notification_dispatches_user_id"), table_name="notification_dispatches")
    op.drop_index(op.f("ix_notification_dispatches_id"), table_name="notification_dispatches")
    op.drop_table("notification_dispatches")
