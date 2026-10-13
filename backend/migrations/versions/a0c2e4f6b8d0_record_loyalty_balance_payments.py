"""Record incoming loyalty payments without expiring settlement money."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "a0c2e4f6b8d0"
down_revision = "f7b9d1e3a5c7"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("loyalty_bonus_credits", sa.Column("moysklad_paymentin_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.create_unique_constraint("uq_loyalty_bonus_credits_paymentin_id", "loyalty_bonus_credits", ["moysklad_paymentin_id"])
    op.alter_column("loyalty_bonus_credits", "expires_at", existing_type=sa.DateTime(timezone=True), nullable=True)


def downgrade():
    op.execute("UPDATE loyalty_bonus_credits SET expires_at = earned_at + interval '60 days' WHERE expires_at IS NULL")
    op.alter_column("loyalty_bonus_credits", "expires_at", existing_type=sa.DateTime(timezone=True), nullable=False)
    op.drop_constraint("uq_loyalty_bonus_credits_paymentin_id", "loyalty_bonus_credits", type_="unique")
    op.drop_column("loyalty_bonus_credits", "moysklad_paymentin_id")
