"""create banners table

Revision ID: f9d2c4b7a1e6
Revises: ed4b7c3a9f12
Create Date: 2026-05-11 16:40:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "f9d2c4b7a1e6"
down_revision: Union[str, Sequence[str], None] = "ed4b7c3a9f12"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if inspector.has_table("banners"):
        return

    op.create_table(
        "banners",
        sa.Column("image_path", sa.String(length=1024), nullable=False),
        sa.Column("inner_link", sa.String(length=2048), nullable=True),
        sa.Column("outer_link", sa.String(length=2048), nullable=True),
        sa.Column("priority", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("archived", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_banners_id"), "banners", ["id"], unique=False)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table("banners"):
        return

    op.drop_index(op.f("ix_banners_id"), table_name="banners")
    op.drop_table("banners")
