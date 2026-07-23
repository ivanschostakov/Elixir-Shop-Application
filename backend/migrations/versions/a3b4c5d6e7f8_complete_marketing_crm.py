"""complete marketing crm

Revision ID: a3b4c5d6e7f8
Revises: f2e3d4c5b6a7
Create Date: 2026-07-23 00:05:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "a3b4c5d6e7f8"
down_revision: str | Sequence[str] | None = "f2e3d4c5b6a7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _table_exists(inspector: sa.Inspector, table_name: str) -> bool:
    return inspector.has_table(table_name)


def _columns(inspector: sa.Inspector, table_name: str) -> set[str]:
    return {column["name"] for column in inspector.get_columns(table_name)} if inspector.has_table(table_name) else set()


def _add_column_if_missing(table_name: str, column: sa.Column) -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if column.name in _columns(inspector, table_name):
        return
    with op.batch_alter_table(table_name) as batch:
        batch.add_column(column)


def _create_index_if_missing(index_name: str, table_name: str, columns: list[str]) -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if any(index["name"] == index_name for index in inspector.get_indexes(table_name)):
        return
    op.create_index(index_name, table_name, columns)


def _foreign_keys(inspector: sa.Inspector, table_name: str) -> set[str]:
    if not inspector.has_table(table_name):
        return set()
    return {constraint["name"] for constraint in inspector.get_foreign_keys(table_name) if constraint["name"]}


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not _table_exists(inspector, "admin_push_campaign_templates"):
        op.create_table(
            "admin_push_campaign_templates",
            sa.Column("code", sa.String(length=80), nullable=False),
            sa.Column("category", sa.String(length=64), nullable=False, server_default=sa.text("'general'")),
            sa.Column("name_ru", sa.String(length=160), nullable=False),
            sa.Column("name_en", sa.String(length=160), nullable=False),
            sa.Column("title_ru", sa.String(length=180), nullable=False),
            sa.Column("title_en", sa.String(length=180), nullable=False),
            sa.Column("body_ru", sa.String(length=500), nullable=False),
            sa.Column("body_en", sa.String(length=500), nullable=False),
            sa.Column("deep_link", sa.String(length=500), nullable=True),
            sa.Column("goal", sa.String(length=120), nullable=True),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("code", name="uq_admin_push_campaign_templates_code"),
        )
        op.create_index("ix_admin_push_campaign_templates_id", "admin_push_campaign_templates", ["id"])
        op.create_index("ix_admin_push_campaign_templates_category", "admin_push_campaign_templates", ["category"])
        op.create_index("ix_admin_push_campaign_templates_is_active", "admin_push_campaign_templates", ["is_active"])
        op.create_index("ix_admin_push_campaign_templates_active_category", "admin_push_campaign_templates", ["is_active", "category"])

    op.execute(sa.text("""
        INSERT INTO admin_push_campaign_templates
            (code, category, name_ru, name_en, title_ru, title_en, body_ru, body_en, deep_link, goal, is_active)
        VALUES
            ('new_arrivals', 'sales', 'Новинки', 'New arrivals', 'Новинки уже в Elixir Shop', 'New arrivals are in Elixir Shop', 'Посмотрите свежие позиции и выберите то, что нужно сейчас.', 'Explore fresh products and pick what you need now.', '/catalog', 'sales', true),
            ('abandoned_cart', 'recovery', 'Брошенная корзина', 'Abandoned cart', 'Вы оставили товары в корзине', 'You left items in your cart', 'Корзина сохранена — можно вернуться и оформить заказ в пару касаний.', 'Your cart is saved — come back and finish checkout in a few taps.', '/basket', 'recovery', true),
            ('repeat_purchase', 'retention', 'Повторная покупка', 'Repeat purchase', 'Пора пополнить запас?', 'Time to restock?', 'Подобрали товары, которые обычно покупают повторно. Загляните в каталог.', 'We picked products customers often reorder. Take a look.', '/catalog', 'retention', true),
            ('review_request', 'loyalty', 'Просьба об отзыве', 'Review request', 'Расскажите, как вам заказ', 'Tell us about your order', 'Ваш отзыв помогает другим клиентам выбрать правильный продукт.', 'Your review helps other customers choose the right product.', '/orders', 'loyalty', true)
        ON CONFLICT (code) DO NOTHING
    """))

    inspector = sa.inspect(bind)
    if _table_exists(inspector, "admin_push_campaigns"):
        _add_column_if_missing("admin_push_campaigns", sa.Column("goal", sa.String(length=120), nullable=True))
        _add_column_if_missing("admin_push_campaigns", sa.Column("utm_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")))
        _add_column_if_missing("admin_push_campaigns", sa.Column("template_id", sa.BigInteger(), nullable=True))
        inspector = sa.inspect(bind)
        if "fk_admin_push_campaigns_template_id" not in _foreign_keys(inspector, "admin_push_campaigns"):
            op.create_foreign_key(
                "fk_admin_push_campaigns_template_id",
                "admin_push_campaigns",
                "admin_push_campaign_templates",
                ["template_id"],
                ["id"],
                ondelete="SET NULL",
            )
        _create_index_if_missing("ix_admin_push_campaigns_template_id", "admin_push_campaigns", ["template_id"])

    if _table_exists(inspector, "admin_push_campaign_recipients"):
        _add_column_if_missing("admin_push_campaign_recipients", sa.Column("opened_at", sa.DateTime(timezone=True), nullable=True))
        _add_column_if_missing("admin_push_campaign_recipients", sa.Column("clicked_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if _table_exists(inspector, "admin_push_campaign_recipients"):
        for column_name in ("clicked_at", "opened_at"):
            if column_name in _columns(inspector, "admin_push_campaign_recipients"):
                with op.batch_alter_table("admin_push_campaign_recipients") as batch:
                    batch.drop_column(column_name)
    if _table_exists(inspector, "admin_push_campaigns"):
        for column_name in ("template_id", "utm_json", "goal"):
            if column_name in _columns(inspector, "admin_push_campaigns"):
                with op.batch_alter_table("admin_push_campaigns") as batch:
                    batch.drop_column(column_name)
    if _table_exists(inspector, "admin_push_campaign_templates"):
        op.drop_table("admin_push_campaign_templates")
