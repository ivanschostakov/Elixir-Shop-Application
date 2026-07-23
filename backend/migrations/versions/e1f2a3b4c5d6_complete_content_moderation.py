"""complete content moderation

Revision ID: e1f2a3b4c5d6
Revises: d4e5f6a7b8c9
Create Date: 2026-07-22 20:20:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "e1f2a3b4c5d6"
down_revision: str | Sequence[str] | None = "d4e5f6a7b8c9"
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

    if _table_exists(inspector, "reviews"):
        _add_column_if_missing("reviews", sa.Column("submitter_ip", sa.String(length=64), nullable=True))
        _add_column_if_missing("reviews", sa.Column("internal_moderation_comment", sa.String(length=4000), nullable=True))
        _add_column_if_missing("reviews", sa.Column("spam_score", sa.Integer(), nullable=False, server_default=sa.text("0")))
        _add_column_if_missing("reviews", sa.Column("profanity_flag", sa.Boolean(), nullable=False, server_default=sa.false()))
        _add_column_if_missing("reviews", sa.Column("duplicate_flag", sa.Boolean(), nullable=False, server_default=sa.false()))
        _add_column_if_missing("reviews", sa.Column("suspicious_ip_flag", sa.Boolean(), nullable=False, server_default=sa.false()))
        _add_column_if_missing("reviews", sa.Column("moderation_flags", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")))
        _add_column_if_missing("reviews", sa.Column("duplicate_group_key", sa.String(length=128), nullable=True))
        _add_column_if_missing("reviews", sa.Column("appeal_status", sa.String(length=32), nullable=False, server_default=sa.text("'none'")))
        _add_column_if_missing("reviews", sa.Column("restored_at", sa.DateTime(timezone=True), nullable=True))
        _add_column_if_missing("reviews", sa.Column("customer_notified_at", sa.DateTime(timezone=True), nullable=True))
        _create_index_if_missing("ix_reviews_submitter_ip", "reviews", ["submitter_ip"])
        _create_index_if_missing("ix_reviews_duplicate_group_key", "reviews", ["duplicate_group_key"])
        _create_index_if_missing("ix_reviews_appeal_status", "reviews", ["appeal_status"])

    if _table_exists(inspector, "review_attachments"):
        _add_column_if_missing("review_attachments", sa.Column("moderation_status", sa.String(length=32), nullable=False, server_default=sa.text("'pending'")))
        _add_column_if_missing("review_attachments", sa.Column("moderated_at", sa.DateTime(timezone=True), nullable=True))
        _add_column_if_missing("review_attachments", sa.Column("moderated_by_user_id", sa.BigInteger(), nullable=True))
        inspector = sa.inspect(bind)
        if "fk_review_attachments_moderated_by_user_id_admins" not in _foreign_keys(inspector, "review_attachments"):
            op.create_foreign_key(
                "fk_review_attachments_moderated_by_user_id_admins",
                "review_attachments",
                "admins",
                ["moderated_by_user_id"],
                ["user_id"],
                ondelete="SET NULL",
            )
        op.execute(sa.text(
            "UPDATE review_attachments AS a "
            "SET moderation_status = 'approved' "
            "FROM reviews AS r "
            "WHERE a.review_id = r.id AND r.moderated = true AND r.rejected_at IS NULL AND a.moderation_status = 'pending'"
        ))
        _create_index_if_missing("ix_review_attachments_moderation_status", "review_attachments", ["moderation_status"])
        _create_index_if_missing("ix_review_attachments_moderated_by_user_id", "review_attachments", ["moderated_by_user_id"])

    if not _table_exists(inspector, "review_moderation_events"):
        op.create_table(
            "review_moderation_events",
            sa.Column("review_id", sa.BigInteger(), nullable=False),
            sa.Column("actor_user_id", sa.BigInteger(), nullable=True),
            sa.Column("action", sa.String(length=80), nullable=False),
            sa.Column("comment", sa.String(length=4000), nullable=True),
            sa.Column("before_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
            sa.Column("after_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
            sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
            sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.ForeignKeyConstraint(["actor_user_id"], ["admins.user_id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["review_id"], ["reviews.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(op.f("ix_review_moderation_events_id"), "review_moderation_events", ["id"])
        op.create_index(op.f("ix_review_moderation_events_review_id"), "review_moderation_events", ["review_id"])
        op.create_index(op.f("ix_review_moderation_events_actor_user_id"), "review_moderation_events", ["actor_user_id"])
        op.create_index(op.f("ix_review_moderation_events_action"), "review_moderation_events", ["action"])

    if _table_exists(inspector, "banners"):
        _add_column_if_missing("banners", sa.Column("desktop_image_path", sa.String(length=1024), nullable=True))
        _add_column_if_missing("banners", sa.Column("mobile_image_path", sa.String(length=1024), nullable=True))
        _add_column_if_missing("banners", sa.Column("title", sa.String(length=240), nullable=True))
        _add_column_if_missing("banners", sa.Column("status", sa.String(length=32), nullable=False, server_default=sa.text("'published'")))
        _add_column_if_missing("banners", sa.Column("starts_at", sa.DateTime(timezone=True), nullable=True))
        _add_column_if_missing("banners", sa.Column("ends_at", sa.DateTime(timezone=True), nullable=True))
        _add_column_if_missing("banners", sa.Column("audience_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")))
        _add_column_if_missing("banners", sa.Column("click_count", sa.Integer(), nullable=False, server_default=sa.text("0")))
        _add_column_if_missing("banners", sa.Column("impression_count", sa.Integer(), nullable=False, server_default=sa.text("0")))
        op.execute(sa.text("UPDATE banners SET status = 'archived' WHERE archived = true AND status = 'published'"))
        _create_index_if_missing("ix_banners_status", "banners", ["status"])
        _create_index_if_missing("ix_banners_starts_at", "banners", ["starts_at"])
        _create_index_if_missing("ix_banners_ends_at", "banners", ["ends_at"])

    if not _table_exists(inspector, "banner_clicks"):
        op.create_table(
            "banner_clicks",
            sa.Column("banner_id", sa.BigInteger(), nullable=False),
            sa.Column("user_id", sa.BigInteger(), nullable=True),
            sa.Column("ip_address", sa.String(length=64), nullable=True),
            sa.Column("user_agent", sa.String(length=512), nullable=True),
            sa.Column("target_url", sa.String(length=2048), nullable=True),
            sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
            sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.ForeignKeyConstraint(["banner_id"], ["banners.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(op.f("ix_banner_clicks_id"), "banner_clicks", ["id"])
        op.create_index(op.f("ix_banner_clicks_banner_id"), "banner_clicks", ["banner_id"])
        op.create_index(op.f("ix_banner_clicks_user_id"), "banner_clicks", ["user_id"])

    if not _table_exists(inspector, "business_content_pages"):
        op.create_table(
            "business_content_pages",
            sa.Column("code", sa.String(length=80), nullable=False),
            sa.Column("title_ru", sa.String(length=240), nullable=False),
            sa.Column("title_en", sa.String(length=240), nullable=False),
            sa.Column("body_ru", sa.Text(), nullable=False, server_default=sa.text("''")),
            sa.Column("body_en", sa.Text(), nullable=False, server_default=sa.text("''")),
            sa.Column("link_url", sa.String(length=2048), nullable=True),
            sa.Column("status", sa.String(length=32), nullable=False, server_default=sa.text("'draft'")),
            sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1")),
            sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
            sa.Column("updated_by_user_id", sa.BigInteger(), nullable=True),
            sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.ForeignKeyConstraint(["updated_by_user_id"], ["admins.user_id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("code"),
        )
        op.create_index(op.f("ix_business_content_pages_id"), "business_content_pages", ["id"])
        op.create_index(op.f("ix_business_content_pages_code"), "business_content_pages", ["code"])
        op.create_index(op.f("ix_business_content_pages_status"), "business_content_pages", ["status"])
        op.create_index(op.f("ix_business_content_pages_updated_by_user_id"), "business_content_pages", ["updated_by_user_id"])
        seed_pages = [
            ("company_details", "Реквизиты компании", "Company details"),
            ("contacts", "Контакты", "Contacts"),
            ("delivery_information", "Информация о доставке", "Delivery information"),
            ("payment_information", "Информация об оплате", "Payment information"),
            ("privacy_policy", "Политика конфиденциальности", "Privacy policy"),
            ("terms_conditions", "Условия использования", "Terms and conditions"),
            ("legal_notices", "Юридические уведомления", "Legal notices"),
        ]
        for code, title_ru, title_en in seed_pages:
            op.execute(sa.text(
                "INSERT INTO business_content_pages (code, title_ru, title_en, status) "
                "VALUES (:code, :title_ru, :title_en, 'draft') "
                "ON CONFLICT (code) DO NOTHING"
            ).bindparams(code=code, title_ru=title_ru, title_en=title_en))

    if not _table_exists(inspector, "business_content_versions"):
        op.create_table(
            "business_content_versions",
            sa.Column("page_id", sa.BigInteger(), nullable=False),
            sa.Column("version", sa.Integer(), nullable=False),
            sa.Column("actor_user_id", sa.BigInteger(), nullable=True),
            sa.Column("snapshot_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
            sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.ForeignKeyConstraint(["actor_user_id"], ["admins.user_id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["page_id"], ["business_content_pages.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(op.f("ix_business_content_versions_id"), "business_content_versions", ["id"])
        op.create_index(op.f("ix_business_content_versions_page_id"), "business_content_versions", ["page_id"])
        op.create_index(op.f("ix_business_content_versions_actor_user_id"), "business_content_versions", ["actor_user_id"])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    for table_name in ("business_content_versions", "business_content_pages", "banner_clicks", "review_moderation_events"):
        if _table_exists(inspector, table_name):
            op.drop_table(table_name)
