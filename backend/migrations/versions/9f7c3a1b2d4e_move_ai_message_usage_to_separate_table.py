"""move ai message usage to separate table

Revision ID: 9f7c3a1b2d4e
Revises: 2d9c8f1a7b3e
Create Date: 2026-05-01 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "9f7c3a1b2d4e"
down_revision: Union[str, Sequence[str], None] = "2d9c8f1a7b3e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

bot_model_enum = postgresql.ENUM("free", "premium", name="bot_model", create_type=False)


def upgrade() -> None:
    op.create_table(
        "ai_message_usage",
        sa.Column("message_id", sa.BigInteger(), nullable=False),
        sa.Column("input_tokens", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("cached_input_tokens", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("output_tokens", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("bot_model", bot_model_enum, nullable=False),
        sa.Column("openai_model", sa.String(length=120), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["message_id"], ["ai_messages.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("message_id"),
    )

    op.execute(
        """
        INSERT INTO ai_message_usage (
            message_id,
            input_tokens,
            cached_input_tokens,
            output_tokens,
            bot_model,
            openai_model,
            created_at,
            updated_at
        )
        SELECT
            ai_messages.id,
            COALESCE(previous_user_message.tokens, 0),
            0,
            COALESCE(ai_messages.tokens, 0),
            ai_messages.bot_model,
            CASE ai_messages.bot_model
                WHEN 'premium' THEN 'gpt-4.1'
                ELSE 'gpt-4.1-mini'
            END,
            ai_messages.created_at,
            ai_messages.updated_at
        FROM ai_messages
        LEFT JOIN LATERAL (
            SELECT user_messages.tokens
            FROM ai_messages AS user_messages
            WHERE user_messages.chat_id = ai_messages.chat_id
              AND user_messages.sender = 'user'
              AND user_messages.id < ai_messages.id
            ORDER BY user_messages.id DESC
            LIMIT 1
        ) AS previous_user_message ON true
        WHERE ai_messages.sender = 'ai'
        """
    )

    op.drop_column("ai_messages", "tokens")
    op.drop_column("ai_messages", "bot_model")


def downgrade() -> None:
    op.add_column(
        "ai_messages",
        sa.Column("bot_model", bot_model_enum, server_default=sa.text("'free'"), nullable=False),
    )
    op.add_column(
        "ai_messages",
        sa.Column("tokens", sa.Integer(), server_default=sa.text("0"), nullable=False),
    )
    op.execute(
        """
        UPDATE ai_messages
        SET
            bot_model = ai_message_usage.bot_model,
            tokens = ai_message_usage.output_tokens
        FROM ai_message_usage
        WHERE ai_message_usage.message_id = ai_messages.id
        """
    )
    op.alter_column("ai_messages", "bot_model", server_default=None)
    op.alter_column("ai_messages", "tokens", server_default=None)
    op.drop_table("ai_message_usage")
