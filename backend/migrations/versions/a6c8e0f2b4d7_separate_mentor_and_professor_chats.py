"""Give the personal mentor a separate history and provider conversation."""
from alembic import op
import sqlalchemy as sa

revision = "a6c8e0f2b4d7"
down_revision = "f5b7d9e1a3c6"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("ai_provider_resources", sa.Column("scope", sa.String(16), nullable=False, server_default="mentor"))
    op.create_check_constraint("ck_ai_provider_resource_scope", "ai_provider_resources", "scope IN ('ordinary', 'mentor')")
    # Resources from a clean professor history stay owned by that history.
    # Mixed historical resources cannot be separated reliably; their remote
    # context is retired below while all local message/attachment IDs survive.
    op.execute("""
        UPDATE ai_provider_resources r SET scope = 'ordinary'
        WHERE r.user_id IS NOT NULL AND EXISTS (SELECT 1 FROM chats c WHERE c.user_id = r.user_id)
          AND NOT EXISTS (SELECT 1 FROM ai_messages m WHERE m.user_id = r.user_id AND m.is_sensitive)
    """)
    op.add_column("chats", sa.Column("scope", sa.String(16), nullable=False, server_default="ordinary"))
    op.drop_index("ix_chats_user_id", table_name="chats")
    op.create_index("ix_chats_user_id", "chats", ["user_id"])
    op.create_unique_constraint("uq_chats_user_scope", "chats", ["user_id", "scope"])
    op.create_check_constraint("ck_chats_scope", "chats", "scope IN ('ordinary', 'mentor')")
    op.execute("""
        INSERT INTO ai_provider_resources (user_id, kind, external_id, status, attempts, next_attempt_at, created_at, updated_at)
        SELECT c.user_id, 'conversation', c.conversation_id, 'pending_delete', 0, now() + interval '10 minutes', now(), now()
        FROM chats c WHERE c.conversation_id NOT LIKE 'reset:%'
          AND EXISTS (SELECT 1 FROM ai_messages m WHERE m.chat_id = c.id AND m.is_sensitive)
        ON CONFLICT (kind, external_id) DO UPDATE SET status = 'pending_delete', next_attempt_at = EXCLUDED.next_attempt_at
    """)
    # Keep every message id, attachment, confirmation and reminder reference.
    # Existing sensitive messages belong to the mentor, never the professor.
    op.execute("""
        INSERT INTO chats (user_id, scope, conversation_id, current_tokens, total_tokens, created_at, updated_at)
        SELECT c.user_id, 'mentor', 'reset:split:mentor:' || c.id, 0, 0, c.created_at, c.updated_at
        FROM chats c WHERE c.scope = 'ordinary'
          AND EXISTS (SELECT 1 FROM ai_messages m WHERE m.chat_id = c.id AND m.is_sensitive)
    """)
    # A mixed remote conversation cannot safely be reused by either persona.
    op.execute("""
        UPDATE chats c SET conversation_id = 'reset:split:ordinary:' || c.id, current_tokens = 0
        WHERE c.scope = 'ordinary' AND EXISTS (
            SELECT 1 FROM ai_messages m WHERE m.chat_id = c.id AND m.is_sensitive)
    """)
    op.execute("""
        UPDATE ai_messages m SET chat_id = c.id FROM chats c
        WHERE m.user_id = c.user_id AND c.scope = 'mentor' AND m.is_sensitive
    """)


def downgrade():
    # Merge local histories without losing records; rebuild the remote context.
    op.execute("""
        INSERT INTO chats (user_id, scope, conversation_id, current_tokens, total_tokens, created_at, updated_at)
        SELECT c.user_id, 'ordinary', 'reset:merge:new:' || c.id, 0, c.total_tokens, c.created_at, c.updated_at
        FROM chats c WHERE c.scope = 'mentor' AND NOT EXISTS (
            SELECT 1 FROM chats o WHERE o.user_id = c.user_id AND o.scope = 'ordinary')
    """)
    op.execute("""
        UPDATE ai_messages m SET chat_id = c.id FROM chats c
        WHERE m.user_id = c.user_id AND c.scope = 'ordinary'
    """)
    op.execute("DELETE FROM chats WHERE scope = 'mentor'")
    op.execute("UPDATE chats SET conversation_id = 'reset:merge:' || id, current_tokens = 0")
    op.drop_constraint("ck_chats_scope", "chats", type_="check")
    op.drop_constraint("uq_chats_user_scope", "chats", type_="unique")
    op.drop_index("ix_chats_user_id", table_name="chats")
    op.create_index("ix_chats_user_id", "chats", ["user_id"], unique=True)
    op.drop_column("chats", "scope")
    op.drop_constraint("ck_ai_provider_resource_scope", "ai_provider_resources", type_="check")
    op.drop_column("ai_provider_resources", "scope")
