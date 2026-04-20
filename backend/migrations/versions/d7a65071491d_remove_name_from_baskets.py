"""remove name from baskets

Revision ID: d7a65071491d
Revises: c87f0fa65e1d
Create Date: 2026-04-05 09:15:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d7a65071491d"
down_revision: Union[str, Sequence[str], None] = "c87f0fa65e1d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


TABLE_NAME = "baskets"
USER_ID_INDEX = "ix_baskets_user_id"


def _column_names(inspector: sa.Inspector, table_name: str) -> set[str]:
    return {column["name"] for column in inspector.get_columns(table_name)}


def _index_map(inspector: sa.Inspector, table_name: str) -> dict[str, dict]:
    return {index["name"]: index for index in inspector.get_indexes(table_name)}


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not inspector.has_table(TABLE_NAME):
        return

    columns = _column_names(inspector, TABLE_NAME)
    if "name" in columns:
        op.drop_column(TABLE_NAME, "name")

    indexes = _index_map(inspector, TABLE_NAME)
    user_id_index = indexes.get(USER_ID_INDEX)
    if user_id_index is None:
        op.create_index(USER_ID_INDEX, TABLE_NAME, ["user_id"], unique=True)
    elif not user_id_index.get("unique", False):
        op.drop_index(USER_ID_INDEX, table_name=TABLE_NAME)
        op.create_index(USER_ID_INDEX, TABLE_NAME, ["user_id"], unique=True)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not inspector.has_table(TABLE_NAME):
        return

    columns = _column_names(inspector, TABLE_NAME)
    if "name" not in columns:
        op.add_column(TABLE_NAME, sa.Column("name", sa.String(length=200), nullable=False, server_default=""))
        op.alter_column(TABLE_NAME, "name", server_default=None)

    indexes = _index_map(inspector, TABLE_NAME)
    user_id_index = indexes.get(USER_ID_INDEX)
    if user_id_index is None:
        op.create_index(USER_ID_INDEX, TABLE_NAME, ["user_id"], unique=False)
    elif user_id_index.get("unique", False):
        op.drop_index(USER_ID_INDEX, table_name=TABLE_NAME)
        op.create_index(USER_ID_INDEX, TABLE_NAME, ["user_id"], unique=False)
