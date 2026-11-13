"""Store one pending recovery code per customer and isolate recovered app passwords."""

from alembic import op
import sqlalchemy as sa

revision = "d3f5a7c9e1b2"
down_revision = "c2e4f6a8b0d1"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("users", sa.Column("app_password_reset_at", sa.DateTime(timezone=True), nullable=True))
    op.create_table(
        "user_password_resets",
        sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("email", sa.String(100), nullable=False),
        sa.Column("code_hash", sa.String(255), nullable=False),
        sa.Column("password_fingerprint", sa.String(64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
    )


def downgrade():
    op.drop_table("user_password_resets")
    op.drop_column("users", "app_password_reset_at")
