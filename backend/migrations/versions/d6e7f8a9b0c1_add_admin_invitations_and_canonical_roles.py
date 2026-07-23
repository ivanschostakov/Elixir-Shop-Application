"""add admin invitations and canonical system roles

Revision ID: d6e7f8a9b0c1
Revises: c5d6e7f8a9b0
Create Date: 2026-07-23 22:15:00.000000
"""

import json

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "d6e7f8a9b0c1"
down_revision = "c5d6e7f8a9b0"
branch_labels = None
depends_on = None


ROLE_DEFINITIONS = {
    "superadmin": ("Суперадминистратор", "Super administrator", ["*"]),
    "sales": (
        "Продажи и CRM",
        "Sales and CRM",
        [
            "dashboard.read",
            "orders.read",
            "orders.transition",
            "orders.recover",
            "customers.read",
            "customers.manage",
            "customers.notes",
            "tasks.read",
            "tasks.manage",
            "segments.read",
            "automation.read",
            "sla.read",
            "alerts.read",
            "ai_chats.read",
            "support.read",
            "support.reply",
            "support.assign",
            "leads.read",
            "leads.manage",
            "analytics.read",
            "exports.read",
        ],
    ),
    "support": (
        "Поддержка",
        "Support",
        [
            "dashboard.read",
            "orders.read",
            "customers.read",
            "customers.notes",
            "tasks.read",
            "tasks.manage",
            "reviews.read",
            "community.read",
            "ai_chats.read",
            "support.read",
            "support.reply",
            "support.assign",
            "leads.read",
            "leads.manage",
            "sla.read",
            "alerts.read",
        ],
    ),
    "content": (
        "Контент и витрина",
        "Content and storefront",
        [
            "dashboard.read",
            "catalog.read",
            "catalog.merchandise",
            "categories.manage",
            "reviews.read",
            "reviews.moderate",
            "banners.manage",
            "alerts.read",
            "exports.read",
        ],
    ),
    "marketing": (
        "Маркетинг",
        "Marketing",
        [
            "dashboard.read",
            "customers.read",
            "catalog.read",
            "reviews.read",
            "referrals.read",
            "notifications.manage",
            "segments.read",
            "segments.manage",
            "campaigns.read",
            "campaigns.manage",
            "campaigns.send",
            "leads.read",
            "ai_chats.read",
            "analytics.read",
            "alerts.read",
            "exports.read",
        ],
    ),
    "logistics": (
        "Логистика и операции",
        "Logistics and operations",
        [
            "dashboard.read",
            "orders.read",
            "orders.transition",
            "orders.recover",
            "customers.read",
            "tasks.read",
            "tasks.manage",
            "catalog.read",
            "automation.read",
            "automation.manage",
            "sla.read",
            "alerts.read",
            "alerts.manage",
            "integrations.read",
            "integrations.retry",
            "exports.read",
        ],
    ),
    "analyst": (
        "Аналитик / аудитор",
        "Analyst / auditor",
        [
            "dashboard.read",
            "orders.read",
            "customers.read",
            "tasks.read",
            "segments.read",
            "campaigns.read",
            "automation.read",
            "sla.read",
            "alerts.read",
            "catalog.read",
            "reviews.read",
            "referrals.read",
            "community.read",
            "ai_chats.read",
            "support.read",
            "leads.read",
            "analytics.read",
            "integrations.read",
            "audit.read",
            "exports.read",
        ],
    ),
}

PREVIOUS_ROLE_DEFINITIONS = {
    "superadmin": ("Суперадминистратор", "Super administrator", ["*"]),
    "sales": (
        "Продажи",
        "Sales",
        [
            "dashboard.read",
            "orders.read",
            "orders.transition",
            "customers.read",
            "customers.notes",
            "exports.read",
            "orders.recover",
            "tasks.read",
            "tasks.manage",
            "segments.read",
            "automation.read",
            "automation.manage",
            "sla.read",
            "alerts.read",
            "support.read",
            "support.reply",
            "support.assign",
            "leads.read",
            "leads.manage",
            "ai_chats.read",
        ],
    ),
    "support": (
        "Поддержка",
        "Support",
        [
            "dashboard.read",
            "orders.read",
            "customers.read",
            "customers.notes",
            "reviews.read",
            "community.read",
            "ai_chats.read",
            "exports.read",
            "tasks.read",
            "tasks.manage",
            "sla.read",
            "alerts.read",
            "support.read",
            "support.reply",
            "support.assign",
            "leads.read",
            "leads.manage",
        ],
    ),
    "content": (
        "Контент",
        "Content",
        [
            "dashboard.read",
            "catalog.read",
            "catalog.merchandise",
            "categories.manage",
            "reviews.read",
            "reviews.moderate",
            "banners.manage",
            "exports.read",
            "alerts.read",
        ],
    ),
    "marketing": (
        "Маркетинг",
        "Marketing",
        [
            "dashboard.read",
            "customers.read",
            "catalog.read",
            "reviews.read",
            "referrals.read",
            "notifications.manage",
            "analytics.read",
            "exports.read",
            "segments.read",
            "segments.manage",
            "campaigns.read",
            "campaigns.manage",
            "campaigns.send",
            "automation.read",
            "automation.manage",
            "alerts.read",
            "leads.read",
        ],
    ),
    "logistics": (
        "Логистика",
        "Logistics",
        [
            "dashboard.read",
            "orders.read",
            "orders.transition",
            "customers.read",
            "catalog.read",
            "integrations.read",
            "integrations.retry",
            "orders.recover",
            "exports.read",
            "tasks.read",
            "tasks.manage",
            "automation.read",
            "automation.manage",
            "sla.read",
            "alerts.read",
            "alerts.manage",
        ],
    ),
    "analyst": (
        "Аналитик",
        "Analyst",
        [
            "dashboard.read",
            "orders.read",
            "customers.read",
            "catalog.read",
            "reviews.read",
            "analytics.read",
            "integrations.read",
            "audit.read",
            "exports.read",
            "segments.read",
            "campaigns.read",
            "automation.read",
            "sla.read",
            "alerts.read",
            "leads.read",
        ],
    ),
}


def _write_roles(definitions: dict[str, tuple[str, str, list[str]]]) -> None:
    statement = sa.text(
        "UPDATE admin_roles SET name_ru = :name_ru, name_en = :name_en, "
        "permissions = CAST(:permissions AS jsonb), is_system = true, updated_at = now() "
        "WHERE code = :code"
    )
    for code, (name_ru, name_en, permissions) in definitions.items():
        op.execute(
            statement.bindparams(
                code=code,
                name_ru=name_ru,
                name_en=name_en,
                permissions=json.dumps(permissions, ensure_ascii=False),
            )
        )


def upgrade() -> None:
    op.create_table(
        "admin_invitations",
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column(
            "role_codes",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column("invited_by_user_id", sa.BigInteger(), nullable=True),
        sa.Column("accepted_by_user_id", sa.BigInteger(), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_sent_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("send_count", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["accepted_by_user_id"], ["admins.user_id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["invited_by_user_id"], ["admins.user_id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash"),
    )
    op.create_index("ix_admin_invitations_id", "admin_invitations", ["id"])
    op.create_index("ix_admin_invitations_email", "admin_invitations", ["email"])
    op.create_index("ix_admin_invitations_token_hash", "admin_invitations", ["token_hash"])
    op.create_index("ix_admin_invitations_invited_by_user_id", "admin_invitations", ["invited_by_user_id"])
    op.create_index("ix_admin_invitations_accepted_by_user_id", "admin_invitations", ["accepted_by_user_id"])
    op.create_index("ix_admin_invitations_expires_at", "admin_invitations", ["expires_at"])
    op.create_index(
        "ix_admin_invitations_status",
        "admin_invitations",
        ["accepted_at", "revoked_at", "expires_at"],
    )
    op.create_index(
        "uq_admin_invitations_pending_email",
        "admin_invitations",
        ["email"],
        unique=True,
        postgresql_where=sa.text("accepted_at IS NULL AND revoked_at IS NULL"),
    )
    _write_roles(ROLE_DEFINITIONS)


def downgrade() -> None:
    _write_roles(PREVIOUS_ROLE_DEFINITIONS)
    op.drop_index("uq_admin_invitations_pending_email", table_name="admin_invitations")
    op.drop_index("ix_admin_invitations_status", table_name="admin_invitations")
    op.drop_index("ix_admin_invitations_expires_at", table_name="admin_invitations")
    op.drop_index("ix_admin_invitations_accepted_by_user_id", table_name="admin_invitations")
    op.drop_index("ix_admin_invitations_invited_by_user_id", table_name="admin_invitations")
    op.drop_index("ix_admin_invitations_token_hash", table_name="admin_invitations")
    op.drop_index("ix_admin_invitations_email", table_name="admin_invitations")
    op.drop_index("ix_admin_invitations_id", table_name="admin_invitations")
    op.drop_table("admin_invitations")
