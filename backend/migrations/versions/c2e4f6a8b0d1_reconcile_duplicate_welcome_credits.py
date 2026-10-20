"""Keep an audit reference when two app accounts share one welcome reward."""

from alembic import op
import sqlalchemy as sa

revision = "c2e4f6a8b0d1"
down_revision = "b1d3f5a7c9e0"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("loyalty_bonus_credits", sa.Column("reconciled_to_credit_id", sa.BigInteger(), nullable=True))
    op.add_column("loyalty_bonus_credits", sa.Column("reconciliation_note", sa.String(length=500), nullable=True))
    op.create_foreign_key(
        "fk_loyalty_credit_reconciled_to", "loyalty_bonus_credits", "loyalty_bonus_credits",
        ["reconciled_to_credit_id"], ["id"], ondelete="SET NULL",
    )


def downgrade():
    op.drop_constraint("fk_loyalty_credit_reconciled_to", "loyalty_bonus_credits", type_="foreignkey")
    op.drop_column("loyalty_bonus_credits", "reconciled_to_credit_id")
    op.drop_column("loyalty_bonus_credits", "reconciliation_note")
