"""Telegram mentor journal and opt-in daily reminder settings."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
revision = "d5f7a9c1e3b5"
down_revision = "c4e6a8b0d2f4"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("telegram_ai_journal",
        sa.Column("id",sa.BigInteger(),primary_key=True),
        sa.Column("telegram_user_id",sa.BigInteger(),nullable=False),
        sa.Column("request_key",sa.String(128),nullable=False),
        sa.Column("kind",sa.String(16),nullable=False),
        sa.Column("status",sa.String(16),nullable=False),
        sa.Column("occurred_at",sa.DateTime(timezone=True),nullable=False),
        sa.Column("data",postgresql.JSONB(),nullable=False,server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at",sa.DateTime(timezone=True),nullable=False,server_default=sa.func.now()),
        sa.Column("updated_at",sa.DateTime(timezone=True),nullable=False,server_default=sa.func.now()),
        sa.UniqueConstraint("telegram_user_id","request_key",name="uq_tg_journal_request"))
    op.create_index("ix_telegram_ai_journal_telegram_user_id","telegram_ai_journal",["telegram_user_id"])
    op.create_index("ix_telegram_ai_journal_occurred_at","telegram_ai_journal",["occurred_at"])
    op.create_table("telegram_ai_reminder_settings",
        sa.Column("telegram_user_id",sa.BigInteger(),primary_key=True,autoincrement=False),
        sa.Column("timezone",sa.String(80),nullable=False,server_default="Europe/Moscow"),
        sa.Column("daily_time",sa.String(5)),sa.Column("next_at",sa.DateTime(timezone=True)),
        sa.Column("created_at",sa.DateTime(timezone=True),nullable=False,server_default=sa.func.now()),
        sa.Column("updated_at",sa.DateTime(timezone=True),nullable=False,server_default=sa.func.now()))
    op.create_index("ix_telegram_ai_reminder_settings_next_at","telegram_ai_reminder_settings",["next_at"])


def downgrade():
    op.drop_table("telegram_ai_reminder_settings")
    op.drop_table("telegram_ai_journal")
