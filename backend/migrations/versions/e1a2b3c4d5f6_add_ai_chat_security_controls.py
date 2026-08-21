"""add AI chat security controls

Revision ID: e1a2b3c4d5f6
Revises: d0e1f2a3b4c6
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "e1a2b3c4d5f6"
down_revision: str | Sequence[str] | None = "d0e1f2a3b4c6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "ai_chat_access_bans",
        sa.Column("ban_type", sa.String(length=16), nullable=False),
        sa.Column("subject", sa.String(length=254), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("created_by_user_id", sa.BigInteger(), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_by_user_id", sa.BigInteger(), nullable=True),
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["admin_identities.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["revoked_by_user_id"], ["admin_identities.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_ai_chat_access_bans_lookup", "ai_chat_access_bans", ["ban_type", "subject", "is_active"])
    op.create_index("ix_ai_chat_access_bans_active", "ai_chat_access_bans", ["is_active", "created_at"])

    op.create_table(
        "ai_chat_security_events",
        sa.Column("event_type", sa.String(length=48), nullable=False),
        sa.Column("outcome", sa.String(length=32), server_default="accepted", nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("ip_address", sa.String(length=64), nullable=False),
        sa.Column("risk_score", sa.Integer(), server_default="0", nullable=False),
        sa.Column("is_suspicious", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("risk_reasons", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column("details_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_ai_chat_security_events_event_type", "ai_chat_security_events", ["event_type"])
    op.create_index("ix_ai_chat_security_events_user_id", "ai_chat_security_events", ["user_id"])
    op.create_index("ix_ai_chat_security_events_ip_address", "ai_chat_security_events", ["ip_address"])
    op.create_index("ix_ai_chat_security_events_user_created", "ai_chat_security_events", ["user_id", "created_at"])
    op.create_index("ix_ai_chat_security_events_ip_created", "ai_chat_security_events", ["ip_address", "created_at"])
    op.create_index("ix_ai_chat_security_events_risk_created", "ai_chat_security_events", ["is_suspicious", "created_at"])


def downgrade() -> None:
    op.drop_table("ai_chat_security_events")
    op.drop_table("ai_chat_access_bans")
