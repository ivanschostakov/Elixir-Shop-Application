"""add server defaults for model defaults

Revision ID: 91b4a6f2d8c1
Revises: e7b8c9d0a1f2, f31e2a4d9b0c
Create Date: 2026-04-29 12:30:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "91b4a6f2d8c1"
down_revision: Union[str, Sequence[str], None] = ("e7b8c9d0a1f2", "f31e2a4d9b0c")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _alter_server_default_if_exists(
    inspector: sa.Inspector,
    table_name: str,
    column_name: str,
    server_default: sa.TextClause | None,
) -> None:
    if not inspector.has_table(table_name):
        return
    columns = {col["name"] for col in inspector.get_columns(table_name)}
    if column_name not in columns:
        return
    op.alter_column(table_name, column_name, server_default=server_default)


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    operations: list[tuple[str, str, sa.TextClause]] = [
        ("users", "is_active", sa.text("true")),
        ("users", "is_verified", sa.text("false")),
        ("email_verification_codes", "attempt_count", sa.text("0")),
        ("products", "in_stock", sa.text("false")),
        ("products", "priority", sa.text("0")),
        ("doses", "stock", sa.text("0")),
        ("reviews", "likes", sa.text("0")),
        ("reviews", "dislikes", sa.text("0")),
        ("reviews", "moderated", sa.text("false")),
        ("delivery_recipients", "phone", sa.text("''")),
        ("delivery_recipients", "email", sa.text("''")),
        ("order_drafts", "status", sa.text("'draft'")),
        ("order_drafts", "items_count", sa.text("0")),
        ("order_drafts", "total_quantity", sa.text("0")),
        ("order_drafts", "basket_subtotal", sa.text("0.00")),
        ("order_drafts", "delivery_total", sa.text("0.00")),
        ("order_drafts", "grand_total", sa.text("0.00")),
        ("order_drafts", "currency", sa.text("'RUB'")),
        ("order_draft_items", "unit_price", sa.text("0.00")),
        ("order_draft_items", "line_total", sa.text("0.00")),
        ("orders", "status", sa.text("'Создан'")),
        ("orders", "items_count", sa.text("0")),
        ("orders", "total_quantity", sa.text("0")),
        ("orders", "basket_subtotal", sa.text("0.00")),
        ("orders", "delivery_total", sa.text("0.00")),
        ("orders", "grand_total", sa.text("0.00")),
        ("orders", "currency", sa.text("'RUB'")),
        ("orders", "selected_delivery_service", sa.text("''")),
        ("orders", "selected_delivery_payload", sa.text("'{}'::jsonb")),
        ("orders", "checkout_snapshot", sa.text("'{}'::jsonb")),
        ("orders", "payment_status", sa.text("'draft'")),
        ("orders", "is_active", sa.text("true")),
        ("orders", "is_paid", sa.text("false")),
        ("orders", "is_canceled", sa.text("false")),
        ("orders", "is_shipped", sa.text("false")),
        ("order_items", "unit_price", sa.text("0.00")),
        ("order_items", "line_total", sa.text("0.00")),
        ("app_promos", "source_kind", sa.text("'app'")),
        ("app_promos", "is_active", sa.text("true")),
        ("app_promos", "stacking_policy", sa.text("'exclusive'")),
        ("order_benefit_applications", "status", sa.text("'applied'")),
        ("business_ledger_entries", "status", sa.text("'posted'")),
        ("website_identities", "group_ids", sa.text("'[]'::json")),
        ("website_identities", "group_names", sa.text("'[]'::json")),
        ("website_identities", "custom_fields", sa.text("'{}'::json")),
        ("website_identities", "discount_groups", sa.text("'[]'::json")),
        ("website_identities", "active_coupons", sa.text("'[]'::json")),
        ("website_identities", "recent_used_coupons", sa.text("'[]'::json")),
        ("website_bonus_accounts", "is_active", sa.text("true")),
        ("website_bonus_accounts", "balance", sa.text("0.00")),
        ("website_discount_entitlements", "source_kind", sa.text("'group'")),
        ("website_discount_entitlements", "is_stackable", sa.text("false")),
        ("website_discount_entitlements", "is_active", sa.text("true")),
        ("website_coupons", "use_count", sa.text("0")),
        ("website_coupons", "is_active", sa.text("true")),
        ("website_sync_events", "status", sa.text("'pending'")),
        ("user_category_recommendation_signals", "view_count", sa.text("0")),
        ("user_product_recommendation_signals", "view_count", sa.text("0")),
        ("user_product_recommendation_signals", "cart_quantity", sa.text("0")),
        ("user_product_recommendation_signals", "purchase_quantity", sa.text("0")),
    ]
    for table_name, column_name, default_expr in operations:
        _alter_server_default_if_exists(inspector, table_name, column_name, default_expr)


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    operations: list[tuple[str, str, None]] = [
        ("user_product_recommendation_signals", "purchase_quantity", None),
        ("user_product_recommendation_signals", "cart_quantity", None),
        ("user_product_recommendation_signals", "view_count", None),
        ("user_category_recommendation_signals", "view_count", None),
        ("website_sync_events", "status", None),
        ("website_coupons", "is_active", None),
        ("website_coupons", "use_count", None),
        ("website_discount_entitlements", "is_active", None),
        ("website_discount_entitlements", "is_stackable", None),
        ("website_discount_entitlements", "source_kind", None),
        ("website_bonus_accounts", "balance", None),
        ("website_bonus_accounts", "is_active", None),
        ("website_identities", "recent_used_coupons", None),
        ("website_identities", "active_coupons", None),
        ("website_identities", "discount_groups", None),
        ("website_identities", "custom_fields", None),
        ("website_identities", "group_names", None),
        ("website_identities", "group_ids", None),
        ("business_ledger_entries", "status", None),
        ("order_benefit_applications", "status", None),
        ("app_promos", "stacking_policy", None),
        ("app_promos", "is_active", None),
        ("app_promos", "source_kind", None),
        ("order_items", "line_total", None),
        ("order_items", "unit_price", None),
        ("orders", "is_shipped", None),
        ("orders", "is_canceled", None),
        ("orders", "is_paid", None),
        ("orders", "is_active", None),
        ("orders", "payment_status", None),
        ("orders", "checkout_snapshot", None),
        ("orders", "selected_delivery_payload", None),
        ("orders", "selected_delivery_service", None),
        ("orders", "currency", None),
        ("orders", "grand_total", None),
        ("orders", "delivery_total", None),
        ("orders", "basket_subtotal", None),
        ("orders", "total_quantity", None),
        ("orders", "items_count", None),
        ("orders", "status", None),
        ("order_draft_items", "line_total", None),
        ("order_draft_items", "unit_price", None),
        ("order_drafts", "currency", None),
        ("order_drafts", "grand_total", None),
        ("order_drafts", "delivery_total", None),
        ("order_drafts", "basket_subtotal", None),
        ("order_drafts", "total_quantity", None),
        ("order_drafts", "items_count", None),
        ("order_drafts", "status", None),
        ("delivery_recipients", "email", None),
        ("delivery_recipients", "phone", None),
        ("reviews", "moderated", None),
        ("reviews", "dislikes", None),
        ("reviews", "likes", None),
        ("doses", "stock", None),
        ("products", "priority", None),
        ("products", "in_stock", None),
        ("email_verification_codes", "attempt_count", None),
        ("users", "is_verified", None),
        ("users", "is_active", None),
    ]
    for table_name, column_name, default_expr in operations:
        _alter_server_default_if_exists(inspector, table_name, column_name, default_expr)
