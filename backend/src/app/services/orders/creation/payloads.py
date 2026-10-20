from decimal import Decimal
from typing import Any
from src.database.models import BasketItem, OrderItem
from src.database.schemas import OrderCreate
from .common import amocrm_client


def _build_order_create_data(*, user_id: int, delivery_address_id: int, recipient_id: int, order_code: str, items_count: int, total_quantity: int, basket_subtotal: Decimal, delivery_total: Decimal, grand_total: Decimal, currency: str, delivery_period_min: int | None, delivery_period_max: int | None, comment: str | None, delivery_string: str, selected_delivery_service: str, selected_delivery_payload: dict[str, Any], checkout_snapshot: dict[str, Any], payment_method: str) -> OrderCreate:
    payment_status = "pending" if payment_method.strip().lower() == "later" else "draft"
    return OrderCreate(draft_id=None, user_id=user_id, delivery_address_id=delivery_address_id, recipient_id=recipient_id, order_code=order_code, status=amocrm_client.STATUS_WORDS.get(amocrm_client.STATUS_IDS["main"], "Создан"), items_count=items_count, total_quantity=total_quantity, basket_subtotal=basket_subtotal, delivery_total=delivery_total, grand_total=grand_total, currency=currency, delivery_period_min=delivery_period_min, delivery_period_max=delivery_period_max, comment=comment, delivery_string=delivery_string, selected_delivery_service=selected_delivery_service, selected_delivery_payload=selected_delivery_payload, checkout_snapshot=checkout_snapshot, payment_method=payment_method, payment_provider=None, payment_status=payment_status, payment_invoice_id=None, payment_paid_at=None, payment_error=None, amocrm_lead_id=None, delivery_created_at=None, delivery_provider_ref=None, yandex_request_id=None, is_active=True, is_paid=False, is_canceled=False, is_shipped=False,)


def _build_order_item_from_draft_item(*, user_id: int, order_id: int, item) -> OrderItem:
    return OrderItem(user_id=user_id, order_id=order_id, product_id=item.product_id, variant_id=item.variant_id, product_name=item.product_name, product_sku=item.product_sku, variant_name=item.variant_name, variant_sku=item.variant_sku, quantity=item.quantity, unit_price=item.unit_price, line_total=item.line_total,)


def _build_order_item_from_basket_row(*, user_id: int, order_id: int, row: tuple[BasketItem, Decimal, Decimal]) -> OrderItem:
    item, unit_price, line_total = row
    return OrderItem(user_id=user_id, order_id=order_id, product_id=item.product_id, variant_id=item.variant_id, product_name=item.product.name, product_sku=item.product.sku, variant_name=item.variant.name, variant_sku=item.variant.sku, quantity=item.quantity, unit_price=unit_price, line_total=line_total,)
