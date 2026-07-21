"""add admin platform and guest review moderation

Revision ID: f7a8b9c0d1e2
Revises: e6b8c0d2f4a5
Create Date: 2026-07-22 12:00:00.000000
"""

import json

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "f7a8b9c0d1e2"
down_revision = "e6b8c0d2f4a5"
branch_labels = None
depends_on = None


ROLE_DEFINITIONS = [
    ("superadmin", "Суперадминистратор", "Super administrator", ["*"]),
    ("sales", "Продажи", "Sales", ["dashboard.read", "orders.read", "orders.transition", "customers.read", "customers.notes", "exports.read"]),
    ("support", "Поддержка", "Support", ["dashboard.read", "orders.read", "customers.read", "customers.notes", "reviews.read", "community.read", "ai_chats.read"]),
    ("content", "Контент", "Content", ["dashboard.read", "catalog.read", "catalog.merchandise", "categories.manage", "reviews.read", "reviews.moderate", "banners.manage"]),
    ("marketing", "Маркетинг", "Marketing", ["dashboard.read", "customers.read", "catalog.read", "reviews.read", "referrals.read", "notifications.manage", "analytics.read", "exports.read"]),
    ("logistics", "Логистика", "Logistics", ["dashboard.read", "orders.read", "orders.transition", "customers.read", "catalog.read", "integrations.read", "integrations.retry"]),
    ("analyst", "Аналитик", "Analyst", ["dashboard.read", "orders.read", "customers.read", "catalog.read", "reviews.read", "analytics.read", "integrations.read", "audit.read", "exports.read"]),
]


def upgrade() -> None:
    op.add_column("admins", sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False))
    op.add_column("admins", sa.Column("totp_secret_encrypted", sa.Text(), nullable=True))
    op.add_column("admins", sa.Column("mfa_confirmed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("admins", sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("admins", sa.Column("locale", sa.String(length=5), server_default=sa.text("'ru'"), nullable=False))

    op.add_column("user_sessions", sa.Column("purpose", sa.String(length=24), server_default=sa.text("'app'"), nullable=False))
    op.add_column("user_sessions", sa.Column("mfa_verified_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_user_sessions_purpose", "user_sessions", ["purpose"])

    op.create_table(
        "admin_roles",
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("name_ru", sa.String(length=120), nullable=False),
        sa.Column("name_en", sa.String(length=120), nullable=False),
        sa.Column("permissions", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column("is_system", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code"),
    )
    op.create_index("ix_admin_roles_code", "admin_roles", ["code"])
    op.create_index("ix_admin_roles_id", "admin_roles", ["id"])

    insert_role = sa.text(
        "INSERT INTO admin_roles (code, name_ru, name_en, permissions, is_system) "
        "VALUES (:code, :name_ru, :name_en, CAST(:permissions AS jsonb), true)"
    )
    for code, name_ru, name_en, permissions in ROLE_DEFINITIONS:
        op.execute(
            insert_role.bindparams(
                code=code,
                name_ru=name_ru,
                name_en=name_en,
                permissions=json.dumps(permissions),
            )
        )

    op.create_table(
        "admin_role_assignments",
        sa.Column("admin_user_id", sa.BigInteger(), nullable=False),
        sa.Column("role_id", sa.BigInteger(), nullable=False),
        sa.Column("assigned_by_user_id", sa.BigInteger(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["admin_user_id"], ["admins.user_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["assigned_by_user_id"], ["admins.user_id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["role_id"], ["admin_roles.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("admin_user_id", "role_id"),
    )
    op.execute(
        "INSERT INTO admin_role_assignments (admin_user_id, role_id, assigned_by_user_id) "
        "SELECT admins.user_id, admin_roles.id, admins.user_id FROM admins "
        "JOIN admin_roles ON admin_roles.code = 'superadmin'"
    )

    op.create_table(
        "admin_audit_logs",
        sa.Column("actor_user_id", sa.BigInteger(), nullable=True),
        sa.Column("action", sa.String(length=120), nullable=False),
        sa.Column("entity_type", sa.String(length=80), nullable=False),
        sa.Column("entity_id", sa.String(length=120), nullable=True),
        sa.Column("before_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("after_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("context_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("ip_address", sa.String(length=64), nullable=True),
        sa.Column("user_agent", sa.String(length=512), nullable=True),
        sa.Column("request_id", sa.String(length=120), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.ForeignKeyConstraint(["actor_user_id"], ["admins.user_id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_admin_audit_logs_action", "admin_audit_logs", ["action"])
    op.create_index("ix_admin_audit_logs_actor_user_id", "admin_audit_logs", ["actor_user_id"])
    op.create_index("ix_admin_audit_logs_created_at", "admin_audit_logs", ["created_at"])
    op.create_index("ix_admin_audit_logs_entity_id", "admin_audit_logs", ["entity_id"])
    op.create_index("ix_admin_audit_logs_entity_type", "admin_audit_logs", ["entity_type"])
    op.create_index("ix_admin_audit_logs_request_id", "admin_audit_logs", ["request_id"])
    op.create_index("ix_admin_audit_actor_created", "admin_audit_logs", ["actor_user_id", "created_at"])
    op.create_index("ix_admin_audit_entity", "admin_audit_logs", ["entity_type", "entity_id", "created_at"])
    op.create_index("ix_admin_audit_logs_id", "admin_audit_logs", ["id"])

    op.create_table(
        "admin_notes",
        sa.Column("customer_user_id", sa.BigInteger(), nullable=False),
        sa.Column("author_user_id", sa.BigInteger(), nullable=True),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["author_user_id"], ["admins.user_id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["customer_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_admin_notes_author_user_id", "admin_notes", ["author_user_id"])
    op.create_index("ix_admin_notes_customer_user_id", "admin_notes", ["customer_user_id"])
    op.create_index("ix_admin_notes_id", "admin_notes", ["id"])

    op.create_table(
        "admin_saved_views",
        sa.Column("owner_user_id", sa.BigInteger(), nullable=False),
        sa.Column("resource", sa.String(length=80), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("state_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("is_shared", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["admins.user_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_admin_saved_views_id", "admin_saved_views", ["id"])
    op.create_index("ix_admin_saved_views_owner_user_id", "admin_saved_views", ["owner_user_id"])
    op.create_index("ix_admin_saved_views_resource", "admin_saved_views", ["resource"])

    op.create_table(
        "integration_runs",
        sa.Column("provider", sa.String(length=80), nullable=False),
        sa.Column("operation", sa.String(length=120), nullable=False),
        sa.Column("status", sa.String(length=32), server_default=sa.text("'running'"), nullable=False),
        sa.Column("requested_by_user_id", sa.BigInteger(), nullable=True),
        sa.Column("attempts", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.Column("counters_json", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("idempotency_key", sa.String(length=160), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.ForeignKeyConstraint(["requested_by_user_id"], ["admins.user_id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("idempotency_key"),
    )
    op.create_index("ix_integration_runs_id", "integration_runs", ["id"])
    op.create_index("ix_integration_runs_operation", "integration_runs", ["operation"])
    op.create_index("ix_integration_runs_provider", "integration_runs", ["provider"])
    op.create_index("ix_integration_runs_requested_by_user_id", "integration_runs", ["requested_by_user_id"])
    op.create_index("ix_integration_runs_started_at", "integration_runs", ["started_at"])
    op.create_index("ix_integration_runs_status", "integration_runs", ["status"])
    op.create_index("ix_integration_runs_provider_started", "integration_runs", ["provider", "started_at"])

    op.alter_column("reviews", "user_id", existing_type=sa.BigInteger(), nullable=True)
    op.drop_constraint("reviews_user_id_fkey", "reviews", type_="foreignkey")
    op.create_foreign_key(
        "reviews_user_id_fkey",
        "reviews",
        "users",
        ["user_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.add_column("reviews", sa.Column("guest_name", sa.String(length=120), nullable=True))
    op.add_column("reviews", sa.Column("guest_email", sa.String(length=320), nullable=True))
    op.add_column("reviews", sa.Column("moderated_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("reviews", sa.Column("moderated_by_user_id", sa.BigInteger(), nullable=True))
    op.add_column("reviews", sa.Column("rejected_at", sa.DateTime(timezone=True), nullable=True))
    op.create_foreign_key("fk_reviews_moderated_by_admin", "reviews", "admins", ["moderated_by_user_id"], ["user_id"], ondelete="SET NULL")
    op.create_index("ix_reviews_moderated_by_user_id", "reviews", ["moderated_by_user_id"])
    op.create_index("ix_reviews_moderation_queue", "reviews", ["moderated", "rejected_at", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_reviews_moderation_queue", table_name="reviews")
    op.drop_index("ix_reviews_moderated_by_user_id", table_name="reviews")
    op.drop_constraint("fk_reviews_moderated_by_admin", "reviews", type_="foreignkey")
    op.drop_column("reviews", "rejected_at")
    op.drop_column("reviews", "moderated_by_user_id")
    op.drop_column("reviews", "moderated_at")
    op.drop_column("reviews", "guest_email")
    op.drop_column("reviews", "guest_name")
    op.execute("DELETE FROM reviews WHERE user_id IS NULL")
    op.drop_constraint("reviews_user_id_fkey", "reviews", type_="foreignkey")
    op.create_foreign_key("reviews_user_id_fkey", "reviews", "users", ["user_id"], ["id"])
    op.alter_column("reviews", "user_id", existing_type=sa.BigInteger(), nullable=False)

    op.drop_table("integration_runs")
    op.drop_table("admin_saved_views")
    op.drop_table("admin_notes")
    op.drop_table("admin_audit_logs")
    op.drop_table("admin_role_assignments")
    op.drop_table("admin_roles")

    op.drop_index("ix_user_sessions_purpose", table_name="user_sessions")
    op.drop_column("user_sessions", "mfa_verified_at")
    op.drop_column("user_sessions", "purpose")
    op.drop_column("admins", "locale")
    op.drop_column("admins", "last_login_at")
    op.drop_column("admins", "mfa_confirmed_at")
    op.drop_column("admins", "totp_secret_encrypted")
    op.drop_column("admins", "is_active")
