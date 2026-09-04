"""Durable conversational companion workflow."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "b3d5f7a9c1e3"
down_revision = "a2c4e6f8b0d2"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "ai_companion_dialogues",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("draft", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("focus", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("last_hint_at", sa.DateTime(timezone=True)),
        sa.Column("introduction_message_id", sa.BigInteger(), sa.ForeignKey("ai_messages.id", ondelete="SET NULL")),
    )


def downgrade():
    op.drop_table("ai_companion_dialogues")
