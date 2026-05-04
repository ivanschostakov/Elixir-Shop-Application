"""rename doses table to variants

Revision ID: 7b4c2a9e1f0d
Revises: 5bc7d4a8f901
Create Date: 2026-05-04 13:20:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "7b4c2a9e1f0d"
down_revision: Union[str, Sequence[str], None] = "5bc7d4a8f901"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_table(inspector: sa.Inspector, table_name: str) -> bool:
    return table_name in inspector.get_table_names()


def _has_index(inspector: sa.Inspector, table_name: str, index_name: str) -> bool:
    return any(index.get("name") == index_name for index in inspector.get_indexes(table_name))


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if _has_table(inspector, "doses") and not _has_table(inspector, "variants"):
        op.rename_table("doses", "variants")
        inspector = sa.inspect(bind)

    if _has_table(inspector, "variants"):
        if _has_index(inspector, "variants", "ix_doses_id"):
            op.execute(sa.text("ALTER INDEX ix_doses_id RENAME TO ix_variants_id"))
        if _has_index(inspector, "variants", "ix_doses_product_id"):
            op.execute(sa.text("ALTER INDEX ix_doses_product_id RENAME TO ix_variants_product_id"))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if _has_table(inspector, "variants"):
        if _has_index(inspector, "variants", "ix_variants_id"):
            op.execute(sa.text("ALTER INDEX ix_variants_id RENAME TO ix_doses_id"))
        if _has_index(inspector, "variants", "ix_variants_product_id"):
            op.execute(sa.text("ALTER INDEX ix_variants_product_id RENAME TO ix_doses_product_id"))

    inspector = sa.inspect(bind)
    if _has_table(inspector, "variants") and not _has_table(inspector, "doses"):
        op.rename_table("variants", "doses")
