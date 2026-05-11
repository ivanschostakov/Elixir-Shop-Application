"""set single active ghk-cu banner

Revision ID: a4b6c8d0e2f1
Revises: f9d2c4b7a1e6
Create Date: 2026-05-11 17:20:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a4b6c8d0e2f1"
down_revision: Union[str, Sequence[str], None] = "f9d2c4b7a1e6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table("banners"):
        return

    op.execute(sa.text("UPDATE banners SET archived = true, updated_at = now()"))

    op.execute(
        sa.text(
            """
            INSERT INTO banners (image_path, inner_link, outer_link, priority, archived, created_at, updated_at)
            VALUES (:image_path, :inner_link, :outer_link, :priority, false, now(), now())
            """
        ).bindparams(
            image_path="/media/banners/ghk-cu-banner.png",
            inner_link="/discover?tab=products&q=ghk-cu",
            outer_link=None,
            priority=1000,
        )
    )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table("banners"):
        return

    op.execute(sa.text("DELETE FROM banners WHERE image_path = :image_path").bindparams(image_path="/media/banners/ghk-cu-banner.png"))
