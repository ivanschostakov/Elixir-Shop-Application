"""add app support, ai visibility permissions and crm leads

Revision ID: c5d6e7f8a9b0
Revises: b4c5d6e7f8a9
Create Date: 2026-07-23 18:30:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "c5d6e7f8a9b0"
down_revision = "b4c5d6e7f8a9"
branch_labels = None
depends_on = None


ROLE_PERMISSIONS = {
    "support": ("support.read", "support.reply", "support.assign", "leads.read", "leads.manage"),
    "sales": ("support.read", "support.reply", "support.assign", "leads.read", "leads.manage", "ai_chats.read"),
    "marketing": ("leads.read",),
    "analyst": ("leads.read",),
}


def upgrade() -> None:
    op.create_table(
        "crm_conversations",
        sa.Column("channel", sa.String(length=32), server_default=sa.text("'app_support'"), nullable=False),
        sa.Column("customer_user_id", sa.BigInteger(), nullable=False),
        sa.Column("subject", sa.String(length=240), nullable=True),
        sa.Column("status", sa.String(length=32), server_default=sa.text("'new'"), nullable=False),
        sa.Column("priority", sa.String(length=24), server_default=sa.text("'normal'"), nullable=False),
        sa.Column("assignee_user_id", sa.BigInteger(), nullable=True),
        sa.Column("sla_policy_id", sa.BigInteger(), nullable=True),
        sa.Column("order_id", sa.BigInteger(), nullable=True),
        sa.Column("response_due_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolution_due_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("first_responded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_message_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("customer_last_read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("admin_last_read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sla_breached_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("customer_unread_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("admin_unread_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("status IN ('new','open','waiting_customer','waiting_team','resolved','spam')", name="ck_crm_conversations_status"),
        sa.CheckConstraint("priority IN ('low','normal','high','urgent')", name="ck_crm_conversations_priority"),
        sa.CheckConstraint("channel = 'app_support'", name="ck_crm_conversations_channel"),
        sa.ForeignKeyConstraint(["assignee_user_id"], ["admins.user_id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["customer_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["order_id"], ["orders.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["sla_policy_id"], ["admin_sla_policies.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_crm_conversations_id", "crm_conversations", ["id"])
    op.create_index("ix_crm_conversations_customer_user_id", "crm_conversations", ["customer_user_id"])
    op.create_index("ix_crm_conversations_assignee_user_id", "crm_conversations", ["assignee_user_id"])
    op.create_index("ix_crm_conversations_sla_policy_id", "crm_conversations", ["sla_policy_id"])
    op.create_index("ix_crm_conversations_order_id", "crm_conversations", ["order_id"])
    op.create_index("ix_crm_conversations_status", "crm_conversations", ["status"])
    op.create_index("ix_crm_conversations_priority", "crm_conversations", ["priority"])
    op.create_index("ix_crm_conversations_last_message_at", "crm_conversations", ["last_message_at"])
    op.create_index("ix_crm_conversations_queue", "crm_conversations", ["status", "priority", "last_message_at"])
    op.create_index("ix_crm_conversations_assignee_status", "crm_conversations", ["assignee_user_id", "status"])
    op.create_index("ix_crm_conversations_customer_status", "crm_conversations", ["customer_user_id", "status"])
    op.create_index("ix_crm_conversations_sla", "crm_conversations", ["status", "response_due_at", "resolution_due_at"])
    op.create_index(
        "uq_crm_conversations_active_customer_channel",
        "crm_conversations",
        ["customer_user_id", "channel"],
        unique=True,
        postgresql_where=sa.text("status NOT IN ('resolved', 'spam')"),
    )

    op.create_table(
        "crm_messages",
        sa.Column("conversation_id", sa.BigInteger(), nullable=False),
        sa.Column("sender_type", sa.String(length=24), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=True),
        sa.Column("admin_user_id", sa.BigInteger(), nullable=True),
        sa.Column("client_message_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("body", sa.Text(), server_default=sa.text("''"), nullable=False),
        sa.Column("is_internal", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("sender_type IN ('user','admin','system')", name="ck_crm_messages_sender"),
        sa.CheckConstraint(
            "(sender_type = 'user' AND user_id IS NOT NULL AND admin_user_id IS NULL AND is_internal = false) "
            "OR (sender_type = 'admin' AND user_id IS NULL) "
            "OR (sender_type = 'system' AND user_id IS NULL AND admin_user_id IS NULL)",
            name="ck_crm_messages_author",
        ),
        sa.ForeignKeyConstraint(["admin_user_id"], ["admins.user_id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["conversation_id"], ["crm_conversations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("client_message_id"),
    )
    op.create_index("ix_crm_messages_id", "crm_messages", ["id"])
    op.create_index("ix_crm_messages_conversation_id", "crm_messages", ["conversation_id"])
    op.create_index("ix_crm_messages_user_id", "crm_messages", ["user_id"])
    op.create_index("ix_crm_messages_admin_user_id", "crm_messages", ["admin_user_id"])
    op.create_index("ix_crm_messages_sender_type", "crm_messages", ["sender_type"])
    op.create_index("ix_crm_messages_conversation_created", "crm_messages", ["conversation_id", "created_at"])
    op.create_index("ix_crm_messages_sender_created", "crm_messages", ["sender_type", "created_at"])

    op.create_table(
        "crm_message_attachments",
        sa.Column("message_id", sa.BigInteger(), nullable=False),
        sa.Column("original_filename", sa.String(length=255), nullable=False),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("mime_type", sa.String(length=120), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["message_id"], ["crm_messages.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_crm_message_attachments_id", "crm_message_attachments", ["id"])
    op.create_index("ix_crm_message_attachments_message_id", "crm_message_attachments", ["message_id"])

    op.create_table(
        "crm_assignment_history",
        sa.Column("conversation_id", sa.BigInteger(), nullable=False),
        sa.Column("from_admin_user_id", sa.BigInteger(), nullable=True),
        sa.Column("to_admin_user_id", sa.BigInteger(), nullable=True),
        sa.Column("changed_by_user_id", sa.BigInteger(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.ForeignKeyConstraint(["changed_by_user_id"], ["admins.user_id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["conversation_id"], ["crm_conversations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["from_admin_user_id"], ["admins.user_id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["to_admin_user_id"], ["admins.user_id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_crm_assignment_history_id", "crm_assignment_history", ["id"])
    op.create_index("ix_crm_assignment_history_conversation_id", "crm_assignment_history", ["conversation_id"])
    op.create_index("ix_crm_assignment_history_conversation_created", "crm_assignment_history", ["conversation_id", "created_at"])

    op.create_table(
        "crm_leads",
        sa.Column("title", sa.String(length=240), nullable=False),
        sa.Column("source", sa.String(length=48), server_default=sa.text("'manual'"), nullable=False),
        sa.Column("status", sa.String(length=32), server_default=sa.text("'new'"), nullable=False),
        sa.Column("priority", sa.String(length=24), server_default=sa.text("'normal'"), nullable=False),
        sa.Column("score", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("customer_user_id", sa.BigInteger(), nullable=True),
        sa.Column("conversation_id", sa.BigInteger(), nullable=True),
        sa.Column("product_id", sa.BigInteger(), nullable=True),
        sa.Column("category_id", sa.BigInteger(), nullable=True),
        sa.Column("owner_user_id", sa.BigInteger(), nullable=True),
        sa.Column("created_by_user_id", sa.BigInteger(), nullable=True),
        sa.Column("converted_order_id", sa.BigInteger(), nullable=True),
        sa.Column("contact_name", sa.String(length=240), nullable=True),
        sa.Column("contact_email", sa.String(length=320), nullable=True),
        sa.Column("contact_phone", sa.String(length=64), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("next_action_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("lost_reason", sa.String(length=500), nullable=True),
        sa.Column("converted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("lost_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("status IN ('new','contacted','interested','waiting','converted','lost')", name="ck_crm_leads_status"),
        sa.CheckConstraint("priority IN ('low','normal','high','urgent')", name="ck_crm_leads_priority"),
        sa.CheckConstraint("score >= 0 AND score <= 100", name="ck_crm_leads_score"),
        sa.CheckConstraint("(status = 'lost' AND lost_reason IS NOT NULL) OR status <> 'lost'", name="ck_crm_leads_lost_reason"),
        sa.CheckConstraint("(status = 'converted' AND converted_order_id IS NOT NULL) OR status <> 'converted'", name="ck_crm_leads_converted_order"),
        sa.ForeignKeyConstraint(["category_id"], ["product_categories.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["conversation_id"], ["crm_conversations.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["converted_order_id"], ["orders.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["admins.user_id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["customer_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["owner_user_id"], ["admins.user_id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in ("id", "source", "status", "priority", "customer_user_id", "conversation_id", "product_id", "category_id", "owner_user_id", "converted_order_id", "next_action_at"):
        op.create_index(f"ix_crm_leads_{column}", "crm_leads", [column])
    op.create_index("ix_crm_leads_pipeline", "crm_leads", ["status", "priority", "next_action_at"])
    op.create_index("ix_crm_leads_owner_status", "crm_leads", ["owner_user_id", "status"])
    op.create_index("ix_crm_leads_customer_status", "crm_leads", ["customer_user_id", "status"])

    op.create_table(
        "crm_lead_stage_history",
        sa.Column("lead_id", sa.BigInteger(), nullable=False),
        sa.Column("from_status", sa.String(length=32), nullable=True),
        sa.Column("to_status", sa.String(length=32), nullable=False),
        sa.Column("changed_by_user_id", sa.BigInteger(), nullable=True),
        sa.Column("reason", sa.String(length=500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.ForeignKeyConstraint(["changed_by_user_id"], ["admins.user_id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["lead_id"], ["crm_leads.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_crm_lead_stage_history_id", "crm_lead_stage_history", ["id"])
    op.create_index("ix_crm_lead_stage_history_lead_id", "crm_lead_stage_history", ["lead_id"])
    op.create_index("ix_crm_lead_stage_history_lead_created", "crm_lead_stage_history", ["lead_id", "created_at"])

    op.create_table(
        "crm_lead_notes",
        sa.Column("lead_id", sa.BigInteger(), nullable=False),
        sa.Column("author_user_id", sa.BigInteger(), nullable=True),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["author_user_id"], ["admins.user_id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["lead_id"], ["crm_leads.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_crm_lead_notes_id", "crm_lead_notes", ["id"])
    op.create_index("ix_crm_lead_notes_lead_id", "crm_lead_notes", ["lead_id"])

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

    op.drop_table("crm_lead_notes")
    op.drop_table("crm_lead_stage_history")
    op.drop_table("crm_leads")
    op.drop_table("crm_assignment_history")
    op.drop_table("crm_message_attachments")
    op.drop_table("crm_messages")
    op.drop_table("crm_conversations")
