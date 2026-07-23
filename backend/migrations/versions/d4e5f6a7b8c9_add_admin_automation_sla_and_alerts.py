"""add admin automation, sla, alerts and dashboard preferences

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-07-22 23:30:00.000000
"""

import json

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "d4e5f6a7b8c9"
down_revision = "c3d4e5f6a7b8"
branch_labels = None
depends_on = None


ROLE_PERMISSIONS = {
    "sales": ("automation.read", "automation.manage", "sla.read", "alerts.read"),
    "support": ("sla.read", "alerts.read"),
    "content": ("alerts.read",),
    "marketing": ("automation.read", "automation.manage", "alerts.read"),
    "logistics": ("automation.read", "automation.manage", "sla.read", "alerts.read", "alerts.manage"),
    "analyst": ("automation.read", "sla.read", "alerts.read"),
}


def upgrade() -> None:
    automation_settings = {
        "restock": {"title": "Товар снова в наличии", "body": "Вариант {variant_name} снова в наличии.", "deep_link": None},
        "inactive_customer": {"title": "Мы соскучились", "body": "Давно не было заказов. Загляните, у нас есть новинки для вас.", "deep_link": None, "after_days": 45, "cooldown_days": 30},
        "abandoned_cart": {"title": "Корзина ждет вас", "body": "Вы добавили товары в корзину, но не завершили заказ.", "deep_link": None, "after_hours": 24, "cooldown_hours": 24},
        "review_reminder": {"title": "Поделитесь отзывом", "body": "Прошел месяц после заказа. Оцените препарат и оставьте отзыв.", "deep_link": None, "after_days": 30},
    }
    update_settings = sa.text(
        "UPDATE admin_marketing_automations SET settings_json = CAST(:settings AS jsonb) "
        "WHERE code = :code AND settings_json = '{}'::jsonb"
    )
    for code, settings in automation_settings.items():
        op.execute(update_settings.bindparams(code=code, settings=json.dumps(settings, ensure_ascii=False)))

    op.create_table(
        "admin_sla_policies",
        sa.Column("priority", sa.String(length=24), nullable=False),
        sa.Column("name_ru", sa.String(length=120), nullable=False),
        sa.Column("name_en", sa.String(length=120), nullable=False),
        sa.Column("response_minutes", sa.Integer(), nullable=False),
        sa.Column("resolution_minutes", sa.Integer(), nullable=False),
        sa.Column("is_enabled", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("priority"),
    )
    op.create_index("ix_admin_sla_policies_id", "admin_sla_policies", ["id"])
    op.create_index("ix_admin_sla_policies_priority", "admin_sla_policies", ["priority"])
    policy_table = sa.table(
        "admin_sla_policies",
        sa.column("priority", sa.String),
        sa.column("name_ru", sa.String),
        sa.column("name_en", sa.String),
        sa.column("response_minutes", sa.Integer),
        sa.column("resolution_minutes", sa.Integer),
        sa.column("is_enabled", sa.Boolean),
    )
    op.bulk_insert(policy_table, [
        {"priority": "urgent", "name_ru": "Срочный", "name_en": "Urgent", "response_minutes": 15, "resolution_minutes": 120, "is_enabled": True},
        {"priority": "high", "name_ru": "Высокий", "name_en": "High", "response_minutes": 60, "resolution_minutes": 480, "is_enabled": True},
        {"priority": "normal", "name_ru": "Обычный", "name_en": "Normal", "response_minutes": 240, "resolution_minutes": 1440, "is_enabled": True},
        {"priority": "low", "name_ru": "Низкий", "name_en": "Low", "response_minutes": 480, "resolution_minutes": 2880, "is_enabled": True},
    ])

    op.add_column("admin_tasks", sa.Column("sla_policy_id", sa.BigInteger(), nullable=True))
    op.add_column("admin_tasks", sa.Column("response_due_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("admin_tasks", sa.Column("resolution_due_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("admin_tasks", sa.Column("first_started_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("admin_tasks", sa.Column("sla_breached_at", sa.DateTime(timezone=True), nullable=True))
    op.create_foreign_key("fk_admin_tasks_sla_policy_id", "admin_tasks", "admin_sla_policies", ["sla_policy_id"], ["id"], ondelete="SET NULL")
    for column in ("sla_policy_id", "response_due_at", "resolution_due_at", "sla_breached_at"):
        op.create_index(f"ix_admin_tasks_{column}", "admin_tasks", [column])
    op.create_index("ix_admin_tasks_sla_status_resolution", "admin_tasks", ["status", "resolution_due_at"])
    op.execute(
        "UPDATE admin_tasks AS task SET "
        "sla_policy_id = policy.id, "
        "response_due_at = task.created_at + policy.response_minutes * interval '1 minute', "
        "resolution_due_at = task.created_at + policy.resolution_minutes * interval '1 minute', "
        "first_started_at = CASE WHEN task.status IN ('in_progress', 'done') THEN task.updated_at ELSE NULL END "
        "FROM admin_sla_policies AS policy WHERE policy.priority = task.priority AND policy.is_enabled = true"
    )

    op.create_table(
        "admin_order_automation_rules",
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_enabled", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("priority", sa.Integer(), server_default=sa.text("100"), nullable=False),
        sa.Column("conditions_json", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("action_json", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("created_by_user_id", sa.BigInteger(), nullable=True),
        sa.Column("last_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_match_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["admins.user_id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_admin_order_automation_rules_id", "admin_order_automation_rules", ["id"])
    op.create_index("ix_admin_order_automation_rules_is_enabled", "admin_order_automation_rules", ["is_enabled"])
    op.create_index("ix_admin_order_automation_rules_created_by_user_id", "admin_order_automation_rules", ["created_by_user_id"])
    op.create_index("ix_admin_order_automation_rules_enabled_priority", "admin_order_automation_rules", ["is_enabled", "priority", "id"])

    op.create_table(
        "admin_order_automation_executions",
        sa.Column("rule_id", sa.BigInteger(), nullable=False),
        sa.Column("order_id", sa.BigInteger(), nullable=False),
        sa.Column("fingerprint", sa.String(length=64), nullable=False),
        sa.Column("action_kind", sa.String(length=40), nullable=False),
        sa.Column("status", sa.String(length=24), server_default=sa.text("'running'"), nullable=False),
        sa.Column("result_json", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("executed_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.ForeignKeyConstraint(["order_id"], ["orders.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["rule_id"], ["admin_order_automation_rules.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("rule_id", "order_id", "fingerprint", name="uq_admin_order_automation_execution"),
    )
    for column in ("id", "rule_id", "order_id", "action_kind", "status", "executed_at"):
        op.create_index(f"ix_admin_order_automation_executions_{column}", "admin_order_automation_executions", [column])
    op.create_index("ix_admin_order_automation_executions_rule_status", "admin_order_automation_executions", ["rule_id", "status", "executed_at"])

    op.create_table(
        "admin_alerts",
        sa.Column("severity", sa.String(length=24), nullable=False),
        sa.Column("source", sa.String(length=40), nullable=False),
        sa.Column("code", sa.String(length=80), nullable=False),
        sa.Column("title_ru", sa.String(length=240), nullable=False),
        sa.Column("title_en", sa.String(length=240), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("entity_type", sa.String(length=80), nullable=True),
        sa.Column("entity_id", sa.String(length=160), nullable=True),
        sa.Column("path", sa.String(length=500), nullable=True),
        sa.Column("fingerprint", sa.String(length=160), nullable=False),
        sa.Column("occurrence_count", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.Column("last_occurred_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_by_user_id", sa.BigInteger(), nullable=True),
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["resolved_by_user_id"], ["admins.user_id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("fingerprint"),
    )
    for column in ("id", "severity", "source", "code", "entity_type", "entity_id", "last_occurred_at", "resolved_at"):
        op.create_index(f"ix_admin_alerts_{column}", "admin_alerts", [column])
    op.create_index("ix_admin_alerts_active_severity", "admin_alerts", ["resolved_at", "severity", "last_occurred_at"])

    op.create_table(
        "admin_alert_read_receipts",
        sa.Column("alert_id", sa.BigInteger(), nullable=False),
        sa.Column("admin_user_id", sa.BigInteger(), nullable=False),
        sa.Column("read_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.ForeignKeyConstraint(["admin_user_id"], ["admins.user_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["alert_id"], ["admin_alerts.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("alert_id", "admin_user_id", name="uq_admin_alert_read_receipt"),
    )
    for column in ("id", "alert_id", "admin_user_id"):
        op.create_index(f"ix_admin_alert_read_receipts_{column}", "admin_alert_read_receipts", [column])

    op.create_table(
        "admin_dashboard_preferences",
        sa.Column("owner_user_id", sa.BigInteger(), nullable=False),
        sa.Column("widgets_json", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["admins.user_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("owner_user_id"),
    )
    op.create_index("ix_admin_dashboard_preferences_id", "admin_dashboard_preferences", ["id"])
    op.create_index("ix_admin_dashboard_preferences_owner_user_id", "admin_dashboard_preferences", ["owner_user_id"])

    for role_code, permissions in ROLE_PERMISSIONS.items():
        for permission in permissions:
            op.execute(
                f"UPDATE admin_roles SET permissions = permissions || '[\"{permission}\"]'::jsonb "
                f"WHERE code = '{role_code}' AND NOT permissions ? '{permission}'"
            )


def downgrade() -> None:
    for role_code, permissions in ROLE_PERMISSIONS.items():
        for permission in permissions:
            op.execute(f"UPDATE admin_roles SET permissions = permissions - '{permission}' WHERE code = '{role_code}'")

    op.execute("UPDATE admin_marketing_automations SET settings_json = '{}'::jsonb WHERE code IN ('restock', 'inactive_customer', 'abandoned_cart', 'review_reminder')")

    op.drop_table("admin_dashboard_preferences")
    op.drop_table("admin_alert_read_receipts")
    op.drop_table("admin_alerts")
    op.drop_table("admin_order_automation_executions")
    op.drop_table("admin_order_automation_rules")
    op.drop_index("ix_admin_tasks_sla_status_resolution", table_name="admin_tasks")
    for column in ("sla_breached_at", "resolution_due_at", "response_due_at", "sla_policy_id"):
        op.drop_index(f"ix_admin_tasks_{column}", table_name="admin_tasks")
    op.drop_constraint("fk_admin_tasks_sla_policy_id", "admin_tasks", type_="foreignkey")
    for column in ("sla_breached_at", "first_started_at", "resolution_due_at", "response_due_at", "sla_policy_id"):
        op.drop_column("admin_tasks", column)
    op.drop_table("admin_sla_policies")
