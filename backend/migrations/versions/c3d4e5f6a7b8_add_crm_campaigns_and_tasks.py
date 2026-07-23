"""add crm campaigns and tasks

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-07-22 22:00:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "c3d4e5f6a7b8"
down_revision = "b2c3d4e5f6a7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "admin_customer_segments",
        sa.Column("owner_user_id", sa.BigInteger(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("filters_json", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("is_shared", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["admins.user_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("owner_user_id", "name", name="uq_admin_customer_segments_owner_name"),
    )
    op.create_index("ix_admin_customer_segments_id", "admin_customer_segments", ["id"])
    op.create_index("ix_admin_customer_segments_owner_user_id", "admin_customer_segments", ["owner_user_id"])

    op.create_table(
        "admin_tasks",
        sa.Column("title", sa.String(length=240), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=24), server_default=sa.text("'open'"), nullable=False),
        sa.Column("priority", sa.String(length=24), server_default=sa.text("'normal'"), nullable=False),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("customer_user_id", sa.BigInteger(), nullable=True),
        sa.Column("order_id", sa.BigInteger(), nullable=True),
        sa.Column("assignee_user_id", sa.BigInteger(), nullable=False),
        sa.Column("created_by_user_id", sa.BigInteger(), nullable=True),
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["assignee_user_id"], ["admins.user_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["admins.user_id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["customer_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["order_id"], ["orders.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in ("id", "status", "priority", "due_at", "customer_user_id", "order_id", "assignee_user_id", "created_by_user_id"):
        op.create_index(f"ix_admin_tasks_{column}", "admin_tasks", [column])
    op.create_index("ix_admin_tasks_assignee_status_due", "admin_tasks", ["assignee_user_id", "status", "due_at"])
    op.create_index("ix_admin_tasks_customer_status", "admin_tasks", ["customer_user_id", "status"])

    op.create_table(
        "admin_push_campaigns",
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("title", sa.String(length=180), nullable=False),
        sa.Column("body", sa.String(length=500), nullable=False),
        sa.Column("deep_link", sa.String(length=500), nullable=True),
        sa.Column("status", sa.String(length=32), server_default=sa.text("'draft'"), nullable=False),
        sa.Column("segment_id", sa.BigInteger(), nullable=True),
        sa.Column("created_by_user_id", sa.BigInteger(), nullable=True),
        sa.Column("audience_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("sent_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("skipped_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("failed_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["admins.user_id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["segment_id"], ["admin_customer_segments.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in ("id", "status", "segment_id", "created_by_user_id", "scheduled_at"):
        op.create_index(f"ix_admin_push_campaigns_{column}", "admin_push_campaigns", [column])
    op.create_index("ix_admin_push_campaigns_status_scheduled", "admin_push_campaigns", ["status", "scheduled_at"])

    op.create_table(
        "admin_push_campaign_recipients",
        sa.Column("campaign_id", sa.BigInteger(), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("status", sa.String(length=24), server_default=sa.text("'pending'"), nullable=False),
        sa.Column("attempts", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["campaign_id"], ["admin_push_campaigns.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("campaign_id", "user_id", name="uq_admin_push_campaign_recipient"),
    )
    for column in ("id", "campaign_id", "user_id", "status"):
        op.create_index(f"ix_admin_push_campaign_recipients_{column}", "admin_push_campaign_recipients", [column])
    op.create_index("ix_admin_push_campaign_recipients_campaign_status", "admin_push_campaign_recipients", ["campaign_id", "status", "id"])

    op.create_table(
        "admin_marketing_automations",
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("name_ru", sa.String(length=160), nullable=False),
        sa.Column("name_en", sa.String(length=160), nullable=False),
        sa.Column("is_enabled", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("settings_json", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("last_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_result_json", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code"),
    )
    op.create_index("ix_admin_marketing_automations_id", "admin_marketing_automations", ["id"])
    op.create_index("ix_admin_marketing_automations_code", "admin_marketing_automations", ["code"])
    automation_table = sa.table(
        "admin_marketing_automations",
        sa.column("code", sa.String),
        sa.column("name_ru", sa.String),
        sa.column("name_en", sa.String),
        sa.column("is_enabled", sa.Boolean),
    )
    op.bulk_insert(automation_table, [
        {"code": "restock", "name_ru": "Товар снова в наличии", "name_en": "Back in stock", "is_enabled": True},
        {"code": "inactive_customer", "name_ru": "Возврат неактивных клиентов", "name_en": "Inactive customer win-back", "is_enabled": True},
        {"code": "abandoned_cart", "name_ru": "Брошенная корзина", "name_en": "Abandoned cart", "is_enabled": True},
        {"code": "review_reminder", "name_ru": "Напоминание об отзыве", "name_en": "Review reminder", "is_enabled": True},
    ])

    op.execute("UPDATE admin_roles SET permissions = permissions || '[\"tasks.read\",\"tasks.manage\",\"segments.read\"]'::jsonb WHERE code = 'sales'")
    op.execute("UPDATE admin_roles SET permissions = permissions || '[\"tasks.read\",\"tasks.manage\"]'::jsonb WHERE code IN ('support', 'logistics')")
    op.execute("UPDATE admin_roles SET permissions = permissions || '[\"segments.read\",\"segments.manage\",\"campaigns.read\",\"campaigns.manage\",\"campaigns.send\"]'::jsonb WHERE code = 'marketing'")
    op.execute("UPDATE admin_roles SET permissions = permissions || '[\"segments.read\",\"campaigns.read\"]'::jsonb WHERE code = 'analyst'")


def downgrade() -> None:
    for code, permissions in (
        ("sales", ("tasks.read", "tasks.manage", "segments.read")),
        ("support", ("tasks.read", "tasks.manage")),
        ("logistics", ("tasks.read", "tasks.manage")),
        ("marketing", ("segments.read", "segments.manage", "campaigns.read", "campaigns.manage", "campaigns.send")),
        ("analyst", ("segments.read", "campaigns.read")),
    ):
        for permission in permissions:
            op.execute(f"UPDATE admin_roles SET permissions = permissions - '{permission}' WHERE code = '{code}'")
    op.drop_table("admin_marketing_automations")
    op.drop_table("admin_push_campaign_recipients")
    op.drop_table("admin_push_campaigns")
    op.drop_table("admin_tasks")
    op.drop_table("admin_customer_segments")
