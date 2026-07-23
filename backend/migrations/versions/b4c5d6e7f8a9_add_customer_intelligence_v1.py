"""add customer intelligence v1

Revision ID: b4c5d6e7f8a9
Revises: a3b4c5d6e7f8
Create Date: 2026-07-23 12:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "b4c5d6e7f8a9"
down_revision: str | Sequence[str] | None = "a3b4c5d6e7f8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "user_devices",
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("installation_id", sa.String(length=128), nullable=False),
        sa.Column("platform", sa.String(length=16), nullable=False),
        sa.Column("app_version", sa.String(length=32), nullable=True),
        sa.Column("app_build", sa.String(length=32), nullable=True),
        sa.Column("os_version", sa.String(length=64), nullable=True),
        sa.Column("device_model", sa.String(length=128), nullable=True),
        sa.Column("language", sa.String(length=16), nullable=True),
        sa.Column("timezone", sa.String(length=64), nullable=True),
        sa.Column("push_permission", sa.String(length=24), server_default=sa.text("'unknown'"), nullable=False),
        sa.Column("install_source", sa.String(length=128), nullable=True),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("last_session_id", sa.String(length=128), nullable=True),
        sa.Column("sessions_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "installation_id", name="uq_user_devices_user_installation"),
    )
    op.create_index("ix_user_devices_id", "user_devices", ["id"])
    op.create_index("ix_user_devices_user_id", "user_devices", ["user_id"])
    op.create_index("ix_user_devices_platform", "user_devices", ["platform"])
    op.create_index("ix_user_devices_app_version", "user_devices", ["app_version"])
    op.create_index("ix_user_devices_push_permission", "user_devices", ["push_permission"])
    op.create_index("ix_user_devices_install_source", "user_devices", ["install_source"])
    op.create_index("ix_user_devices_platform_version", "user_devices", ["platform", "app_version"])
    op.create_index("ix_user_devices_user_last_seen", "user_devices", ["user_id", "last_seen_at"])

    op.create_table(
        "customer_marketing_profiles",
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("lifecycle_stage", sa.String(length=32), server_default=sa.text("'new'"), nullable=False),
        sa.Column("lead_score", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("engagement_score", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_event_name", sa.String(length=64), nullable=True),
        sa.Column("last_platform", sa.String(length=16), nullable=True),
        sa.Column("last_app_version", sa.String(length=32), nullable=True),
        sa.Column("push_permission", sa.String(length=24), server_default=sa.text("'unknown'"), nullable=False),
        sa.Column("preferred_language", sa.String(length=16), nullable=True),
        sa.Column("timezone", sa.String(length=64), nullable=True),
        sa.Column("sessions_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("total_events", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("product_views", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("category_views", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("searches_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("banner_clicks", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("push_opens", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("push_clicks", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("cart_adds", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("cart_removes", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("checkout_started", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("checkout_failed", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("orders_created", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("orders_paid", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("last_purchase_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id"),
    )
    op.create_index("ix_customer_marketing_profiles_lifecycle_stage", "customer_marketing_profiles", ["lifecycle_stage"])
    op.create_index("ix_customer_marketing_profiles_lead_score", "customer_marketing_profiles", ["lead_score"])
    op.create_index("ix_customer_marketing_profiles_last_seen_at", "customer_marketing_profiles", ["last_seen_at"])
    op.create_index("ix_customer_marketing_profiles_last_platform", "customer_marketing_profiles", ["last_platform"])
    op.create_index("ix_customer_marketing_profiles_last_app_version", "customer_marketing_profiles", ["last_app_version"])
    op.create_index("ix_customer_marketing_profiles_push_permission", "customer_marketing_profiles", ["push_permission"])

    op.create_table(
        "customer_consents",
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("purpose", sa.String(length=32), nullable=False),
        sa.Column("channel", sa.String(length=24), server_default=sa.text("'all'"), nullable=False),
        sa.Column("is_granted", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("source", sa.String(length=32), server_default=sa.text("'app'"), nullable=False),
        sa.Column("policy_version", sa.String(length=32), nullable=True),
        sa.Column("granted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_changed_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "purpose", "channel", name="uq_customer_consents_user_purpose_channel"),
    )
    op.create_index("ix_customer_consents_id", "customer_consents", ["id"])
    op.create_index("ix_customer_consents_user_id", "customer_consents", ["user_id"])
    op.create_index("ix_customer_consents_purpose_granted", "customer_consents", ["purpose", "is_granted"])

    op.create_table(
        "customer_attribution",
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("first_source", sa.String(length=128), nullable=True),
        sa.Column("first_medium", sa.String(length=128), nullable=True),
        sa.Column("first_campaign", sa.String(length=160), nullable=True),
        sa.Column("first_content", sa.String(length=160), nullable=True),
        sa.Column("first_term", sa.String(length=160), nullable=True),
        sa.Column("first_referrer", sa.String(length=500), nullable=True),
        sa.Column("first_landing_page", sa.String(length=500), nullable=True),
        sa.Column("first_touch_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_source", sa.String(length=128), nullable=True),
        sa.Column("last_medium", sa.String(length=128), nullable=True),
        sa.Column("last_campaign", sa.String(length=160), nullable=True),
        sa.Column("last_content", sa.String(length=160), nullable=True),
        sa.Column("last_term", sa.String(length=160), nullable=True),
        sa.Column("last_referrer", sa.String(length=500), nullable=True),
        sa.Column("last_landing_page", sa.String(length=500), nullable=True),
        sa.Column("last_touch_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("install_source", sa.String(length=128), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id"),
    )
    op.create_index("ix_customer_attribution_first_source", "customer_attribution", ["first_source"])
    op.create_index("ix_customer_attribution_first_campaign", "customer_attribution", ["first_campaign"])
    op.create_index("ix_customer_attribution_last_source", "customer_attribution", ["last_source"])
    op.create_index("ix_customer_attribution_last_campaign", "customer_attribution", ["last_campaign"])
    op.create_index("ix_customer_attribution_install_source", "customer_attribution", ["install_source"])

    op.create_table(
        "user_events",
        sa.Column("event_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("device_id", sa.BigInteger(), nullable=True),
        sa.Column("event_name", sa.String(length=64), nullable=False),
        sa.Column("source", sa.String(length=32), server_default=sa.text("'app'"), nullable=False),
        sa.Column("session_id", sa.String(length=128), nullable=True),
        sa.Column("entity_type", sa.String(length=32), nullable=True),
        sa.Column("entity_id", sa.BigInteger(), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("properties_json", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("attribution_json", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.ForeignKeyConstraint(["device_id"], ["user_devices.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("event_id"),
    )
    op.create_index("ix_user_events_id", "user_events", ["id"])
    op.create_index("ix_user_events_event_id", "user_events", ["event_id"])
    op.create_index("ix_user_events_user_id", "user_events", ["user_id"])
    op.create_index("ix_user_events_device_id", "user_events", ["device_id"])
    op.create_index("ix_user_events_event_name", "user_events", ["event_name"])
    op.create_index("ix_user_events_source", "user_events", ["source"])
    op.create_index("ix_user_events_session_id", "user_events", ["session_id"])
    op.create_index("ix_user_events_occurred_at", "user_events", ["occurred_at"])
    op.create_index("ix_user_events_received_at", "user_events", ["received_at"])
    op.create_index("ix_user_events_user_occurred", "user_events", ["user_id", "occurred_at"])
    op.create_index("ix_user_events_name_occurred", "user_events", ["event_name", "occurred_at"])
    op.create_index("ix_user_events_entity", "user_events", ["entity_type", "entity_id"])


def downgrade() -> None:
    op.drop_table("user_events")
    op.drop_table("customer_attribution")
    op.drop_table("customer_consents")
    op.drop_table("customer_marketing_profiles")
    op.drop_table("user_devices")
