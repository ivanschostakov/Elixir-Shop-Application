"""Application companion state, revision a2c4e6f8b0d2."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "a2c4e6f8b0d2"
down_revision = "f4a5b6c7d8e9"
branch_labels = None
depends_on = None


def base():
    return [sa.Column("id", sa.BigInteger(), primary_key=True), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now())]


def user(nullable=False):
    return sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("users.id", ondelete="SET NULL" if nullable else "CASCADE"), nullable=nullable)


def data(name="data", default=None):
    return sa.Column(name, postgresql.JSONB(), nullable=False, server_default=sa.text(default) if default else None)


def integer(name, default="1"):
    return sa.Column(name, sa.Integer(), nullable=False, server_default=default)


def string(name, length=24):
    return sa.Column(name, sa.String(length), nullable=False)


def upgrade():
    op.create_table("ai_companion_profiles", *base(), user(), sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()), integer("version"), data(default="'{}'::jsonb"), data("settings", "'{}'::jsonb"), data("target_history", "'[]'::jsonb"), sa.UniqueConstraint("user_id"))
    op.create_table("ai_companion_plans", *base(), user(), string("course_key", 36), integer("version"), string("status"), sa.Column("is_current", sa.Boolean(), nullable=False, server_default=sa.true()), data(), sa.UniqueConstraint("user_id", "course_key", "version", name="uq_companion_plan_version"))
    op.create_index("uq_companion_current_plan", "ai_companion_plans", ["user_id"], unique=True, postgresql_where=sa.text("is_current AND status IN ('active', 'paused')"))
    op.create_table("ai_companion_events", *base(), user(), sa.Column("plan_id", sa.BigInteger(), sa.ForeignKey("ai_companion_plans.id", ondelete="CASCADE"), nullable=False), string("event_key", 160), sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=False), string("status"), sa.Column("occurred_at", sa.DateTime(timezone=True)), data(), integer("version"), sa.UniqueConstraint("plan_id", "event_key", name="uq_companion_event"))
    op.create_table("ai_companion_entries", *base(), user(), string("kind"), sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False), data(), string("source"), sa.Column("source_message_id", sa.BigInteger(), sa.ForeignKey("ai_messages.id", ondelete="SET NULL")), integer("version"))
    op.create_table("ai_companion_reminders", *base(), user(), sa.Column("event_id", sa.BigInteger(), sa.ForeignKey("ai_companion_events.id", ondelete="CASCADE")), string("kind"), string("dedupe_key", 200), sa.Column("due_at", sa.DateTime(timezone=True), nullable=False), string("status"), integer("attempts", "0"), sa.Column("message_id", sa.BigInteger(), sa.ForeignKey("ai_messages.id", ondelete="SET NULL")), sa.Column("next_attempt_at", sa.DateTime(timezone=True)), sa.UniqueConstraint("user_id", "dedupe_key", name="uq_companion_reminder"))
    op.create_table("ai_provider_resources", *base(), user(True), string("kind"), string("external_id", 200), string("status"), integer("attempts", "0"), sa.Column("next_attempt_at", sa.DateTime(timezone=True)), sa.UniqueConstraint("kind", "external_id", name="uq_ai_provider_resource"))
    op.create_table("ai_companion_operations", *base(), user(), string("request_key", 64), string("fingerprint", 64), data("result"), sa.UniqueConstraint("user_id", "request_key", name="uq_companion_operation"))
    for table in ("ai_companion_plans", "ai_companion_events", "ai_companion_entries", "ai_companion_reminders", "ai_provider_resources", "ai_companion_operations"):
        op.create_index(f"ix_{table}_user_id", table, ["user_id"])
    for table, column in (("ai_companion_events", "scheduled_at"), ("ai_companion_events", "plan_id"), ("ai_companion_entries", "occurred_at"), ("ai_companion_reminders", "due_at")):
        op.create_index(f"ix_{table}_{column}", table, [column])
    op.add_column("ai_messages", sa.Column("client_request_id", sa.String(64)))
    op.add_column("ai_messages", sa.Column("is_sensitive", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.create_unique_constraint("uq_ai_message_client_request", "ai_messages", ["user_id", "client_request_id"])
    op.add_column("attachments", sa.Column("is_private", sa.Boolean(), nullable=False, server_default=sa.false()))


def downgrade():
    op.drop_column("attachments", "is_private")
    op.drop_constraint("uq_ai_message_client_request", "ai_messages", type_="unique")
    op.drop_column("ai_messages", "is_sensitive")
    op.drop_column("ai_messages", "client_request_id")
    for table in ("ai_companion_operations", "ai_provider_resources", "ai_companion_reminders", "ai_companion_entries", "ai_companion_events", "ai_companion_plans", "ai_companion_profiles"):
        op.drop_table(table)
