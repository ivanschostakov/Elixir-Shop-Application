"""drop recipient fields from delivery addresses

Revision ID: f0f46420ee89
Revises: f31e2a4d9b0c
Create Date: 2026-04-20 17:11:53.059380

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f0f46420ee89'
down_revision: Union[str, Sequence[str], None] = 'f31e2a4d9b0c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


DELIVERY_ADDRESS_TABLES = (
    "cdek_pickup_addresses",
    "yandex_pickup_addresses",
    "cdek_door_addresses",
    "yandex_door_addresses",
)


def upgrade() -> None:
    """Upgrade schema."""
    for table_name in DELIVERY_ADDRESS_TABLES:
        op.drop_column(table_name, "email")
        op.drop_column(table_name, "phone")
        op.drop_column(table_name, "full_name")


def downgrade() -> None:
    """Downgrade schema."""
    for table_name in DELIVERY_ADDRESS_TABLES:
        op.add_column(
            table_name,
            sa.Column("full_name", sa.String(length=100), nullable=False, server_default=""),
        )
        op.add_column(
            table_name,
            sa.Column("phone", sa.String(length=20), nullable=False, server_default=""),
        )
        op.add_column(
            table_name,
            sa.Column("email", sa.String(length=100), nullable=False, server_default=""),
        )
        op.alter_column(table_name, "full_name", server_default=None)
        op.alter_column(table_name, "phone", server_default=None)
        op.alter_column(table_name, "email", server_default=None)
