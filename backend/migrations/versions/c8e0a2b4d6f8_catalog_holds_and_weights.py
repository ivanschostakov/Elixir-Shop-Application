"""Track unexported stock holds and actual shipping weights."""
from alembic import op
import sqlalchemy as sa
revision = "c8e0a2b4d6f8"
down_revision = "b7d9e1f3a5c7"
branch_labels = None
depends_on = None
def upgrade():
    op.add_column("variants", sa.Column("local_reserved", sa.Integer, server_default="0", nullable=False))
    op.add_column("variants", sa.Column("weight_grams", sa.Integer))
    op.add_column("order_items", sa.Column("weight_grams", sa.Integer))
def downgrade():
    op.drop_column("order_items", "weight_grams")
    op.drop_column("variants", "weight_grams")
    op.drop_column("variants", "local_reserved")
