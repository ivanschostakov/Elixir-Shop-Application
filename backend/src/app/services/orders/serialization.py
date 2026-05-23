from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.models import Order, OrderItem, Product, Variant
from src.database.models.orders.history import get_order_history_bucket, get_order_status_code
from src.database.schemas import OrderItemRead, OrderRead
from .serialization_utils import build_order_item_image_url, get_products_by_id, get_variants_by_id


def _serialize_order_item(request: Request, item: OrderItem, *, products_by_id: dict[int, Product], variants_by_id: dict[int, Variant]) -> OrderItemRead:
    variant = variants_by_id.get(item.variant_id)
    product = products_by_id.get(item.product_id)
    if product is None and variant is not None:
        product = variant.product
    return OrderItemRead(
        id=item.id,
        user_id=item.user_id,
        order_id=item.order_id,
        product_id=item.product_id,
        variant_id=item.variant_id,
        product_name=item.product_name,
        product_sku=item.product_sku,
        variant_name=item.variant_name,
        variant_sku=item.variant_sku,
        quantity=item.quantity,
        unit_price=item.unit_price,
        line_total=item.line_total,
        image_url=build_order_item_image_url(request, product=product, variant=variant),
        created_at=item.created_at,
        updated_at=item.updated_at,
    )


def _serialize_order(request: Request, order: Order, *, products_by_id: dict[int, Product], variants_by_id: dict[int, Variant]) -> OrderRead:
    items = [_serialize_order_item(request, item, products_by_id=products_by_id, variants_by_id=variants_by_id) for item in order.items]
    return OrderRead(
        id=order.id,
        order_code=order.order_code,
        order_number=order.order_number,
        draft_id=order.draft_id,
        user_id=order.user_id,
        delivery_address_id=order.delivery_address_id,
        recipient_id=order.recipient_id,
        status=order.status,
        items_count=order.items_count,
        total_quantity=order.total_quantity,
        basket_subtotal=order.basket_subtotal,
        delivery_total=order.delivery_total,
        grand_total=order.grand_total,
        currency=order.currency,
        delivery_period_min=order.delivery_period_min,
        delivery_period_max=order.delivery_period_max,
        comment=order.comment,
        delivery_string=order.delivery_string,
        selected_delivery_service=order.selected_delivery_service,
        selected_delivery_payload=order.selected_delivery_payload,
        checkout_snapshot=order.checkout_snapshot,
        payment_method=order.payment_method,
        payment_provider=order.payment_provider,
        payment_status=order.payment_status,
        payment_invoice_id=order.payment_invoice_id,
        payment_paid_at=order.payment_paid_at,
        payment_error=order.payment_error,
        amocrm_lead_id=order.amocrm_lead_id,
        delivery_created_at=order.delivery_created_at,
        delivery_provider_ref=order.delivery_provider_ref,
        yandex_request_id=order.yandex_request_id,
        is_active=order.is_active,
        is_paid=order.is_paid,
        is_canceled=order.is_canceled,
        is_shipped=order.is_shipped,
        status_code=get_order_status_code(order),
        history_bucket=get_order_history_bucket(order),
        delivery_address=order.delivery_address,
        recipient=order.recipient,
        items=items,
        created_at=order.created_at,
        updated_at=order.updated_at,
    )


async def serialize_orders(request: Request, session: AsyncSession, orders: list[Order]) -> list[OrderRead]:
    if not orders:
        return []
    product_ids = {item.product_id for order in orders for item in order.items}
    variant_ids = {item.variant_id for order in orders for item in order.items}
    products_by_id = await get_products_by_id(session, product_ids)
    variants_by_id = await get_variants_by_id(session, variant_ids)
    return [_serialize_order(request, order, products_by_id=products_by_id, variants_by_id=variants_by_id) for order in orders]


async def serialize_order(request: Request, session: AsyncSession, order: Order) -> OrderRead:
    serialized_orders = await serialize_orders(request, session, [order])
    return serialized_orders[0]
