from decimal import Decimal
from types import SimpleNamespace
from fastapi import HTTPException
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status
from src.app.services.benefits.money import quantize_money
from src.app.services.benefits.redemption import redeem_order_bonus_safe
from src.app.services.discounts import discountable_subtotal_for_lines
from src.app.services.catalog_merchandising import catalog_unit_price
from src.app.services.catalog_access import require_catalog_products
from src.app.services.delivery_quotes import calculate_authoritative_cdek_quote
from src.app.services.recommendations import record_purchase
from src.app.services.stock_visibility import get_stock_visibility_policy
from src.database.crud import create_order, get_basket_by_user_id, get_order_by_id
from src.database.models import BasketItem, Order, User
from src.integrations.moysklad.order_sync import sync_order_to_moysklad_safe
from src.app.services.orders.common import _delivery_string, _require_recipient_phone
from src.app.services.orders.crm import ensure_order_has_amocrm_lead
from src.app.services.orders.fulfillment_payloads import normalize_address_for_cf
from src.app.services.orders.settlement_payment import serialized_settlement_checkout
from .helpers import _generate_order_code, _get_or_create_self_recipient
from .delivery import _build_selected_delivery_payload
from .snapshots import _build_checkout_snapshot
from .benefits import _persist_order_benefit_applications, _resolve_checkout_benefits
from .payloads import _build_order_create_data, _build_order_item_from_basket_row


@serialized_settlement_checkout
async def create_order_from_basket_for_user(session: AsyncSession, *, user: User, payment_method: str, entered_code: str | None = None, use_bonus_rubles: bool = False, reward_mode: str | None = None, client_platform: str | None = None) -> Order:
    user_id = int(user.__dict__.get("id") or user.id)
    basket = await get_basket_by_user_id(session, user_id)
    if basket is None or not basket.items: raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Basket is empty")
    await require_catalog_products(session, (item.product_id for item in basket.items),
                                   user_id=user_id, client_platform=client_platform)
    if basket.delivery_address is None: raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Delivery address is required")

    if basket.recipient is None:
        recipient = await _get_or_create_self_recipient(session, user=user)
        basket.recipient_id = recipient.id
        basket.recipient = recipient
        await session.flush()

    basket.recipient.phone = _require_recipient_phone(basket.recipient.phone)
    basket_subtotal = Decimal("0.00")
    total_quantity = 0
    snapshot_items = []
    order_item_rows: list[tuple[BasketItem, Decimal, Decimal]] = []
    stock_policy = await get_stock_visibility_policy(session)

    for basket_item in basket.items:
        variant = basket_item.variant
        visible_stock = stock_policy.visible_stock(variant.stock if variant is not None else 0, basket_item.product,)
        if variant is None or variant.archived or visible_stock <= 0 or basket_item.quantity > visible_stock: raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Basket contains unavailable items")

        unit_price = catalog_unit_price(variant.price, basket_item.product)
        line_total = unit_price * basket_item.quantity
        basket_subtotal += line_total
        total_quantity += basket_item.quantity
        order_item_rows.append((basket_item, unit_price, line_total))
        snapshot_items.append(SimpleNamespace(product_id=basket_item.product_id, variant_id=basket_item.variant_id, product_name=basket_item.product.name, product_sku=basket_item.product.sku, variant_name=variant.name, quantity=basket_item.quantity, unit_price=unit_price, line_total=line_total,))

    if str(basket.delivery_address.provider).upper() == "CDEK":
        authoritative_quote = await calculate_authoritative_cdek_quote(session, user=user, address=basket.delivery_address, items=basket.items,)
        basket.delivery_total = Decimal(str(authoritative_quote["delivery_sum"]))
        basket.currency = str(authoritative_quote["currency"])
        basket.delivery_period_min = int(authoritative_quote["period_min"])
        basket.delivery_period_max = int(authoritative_quote["period_max"])
        await session.flush()

    checkout_source = SimpleNamespace(delivery_address=basket.delivery_address, delivery_address_id=basket.delivery_address_id, recipient=basket.recipient, recipient_id=basket.recipient_id, items=snapshot_items, basket_subtotal=basket_subtotal, delivery_total=basket.delivery_total, grand_total=basket_subtotal + basket.delivery_total, currency=basket.currency, delivery_period_min=basket.delivery_period_min, delivery_period_max=basket.delivery_period_max, comment=None,)
    selected_delivery_service, selected_delivery_payload = await _build_selected_delivery_payload(checkout_source)
    discountable_subtotal = await discountable_subtotal_for_lines(session, ((item.product_id, line_total) for item, _, line_total in order_item_rows),)
    resolved_benefits = await _resolve_checkout_benefits(
        session,
        user=user,
        subtotal=basket_subtotal,
        discountable_subtotal=discountable_subtotal,
        delivery_total=basket.delivery_total,
        currency=basket.currency,
        entered_code=entered_code,
        quote_items=[
            {
                "variant_system_id": str(item.variant.system_id),
                "product_system_id": str(item.product.system_id),
                "sku": item.variant.sku or item.product.sku,
                "quantity": item.quantity,
            }
            for item, _, _ in order_item_rows
        ],
        use_bonus_rubles=use_bonus_rubles,
        reward_mode=reward_mode,
    )
    grand_total = (quantize_money(resolved_benefits["cash_total"]) if resolved_benefits.get("cash_total") is not None else (quantize_money(resolved_benefits["total_after_discounts"]) or Decimal("0.00")) + basket.delivery_total)
    checkout_snapshot = _build_checkout_snapshot(checkout_source, client_platform=client_platform, payment_method=payment_method, selected_delivery_service=selected_delivery_service, selected_delivery_payload=selected_delivery_payload, resolved_benefits=resolved_benefits,)
    delivery_string = _delivery_string(selected_delivery_service, normalize_address_for_cf(selected_delivery_payload.get("address")))

    order_code = await _generate_order_code(session)
    order_create = _build_order_create_data(user_id=user_id, delivery_address_id=basket.delivery_address_id, recipient_id=basket.recipient_id, order_code=order_code, items_count=len(order_item_rows), total_quantity=total_quantity, basket_subtotal=basket_subtotal, delivery_total=basket.delivery_total, grand_total=grand_total, currency=basket.currency, delivery_period_min=basket.delivery_period_min, delivery_period_max=basket.delivery_period_max, comment=None, delivery_string=delivery_string, selected_delivery_service=selected_delivery_service, selected_delivery_payload=selected_delivery_payload, checkout_snapshot=checkout_snapshot, payment_method=payment_method,)
    order = await create_order(session, order_create, commit=False)
    order_items = [_build_order_item_from_basket_row(user_id=user_id, order_id=order.id, row=row) for row in order_item_rows]
    session.add_all(order_items)
    await session.flush()
    await _persist_order_benefit_applications(session, order=order, user=user, resolved_benefits=resolved_benefits)
    for item, _, _ in order_item_rows: await record_purchase(session, user_id=user_id, product_id=item.product_id, quantity=item.quantity, commit=False)
    await ensure_order_has_amocrm_lead(session, order, user=user)
    await session.execute(delete(BasketItem).where(BasketItem.basket_id == basket.id))
    basket.delivery_address_id = None
    basket.recipient_id = None
    basket.delivery_total = Decimal("0.00")
    basket.currency = "RUB"
    basket.delivery_period_min = None
    basket.delivery_period_max = None
    await session.commit()

    created_order = await get_order_by_id(session, order.id, user_id=user_id)
    if created_order is None: raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to load created order")
    created_order_id = int(order.__dict__.get("id") or created_order.__dict__.get("id") or created_order.id)
    await redeem_order_bonus_safe(session, order=created_order, user=user)
    created_order = await get_order_by_id(session, created_order_id, user_id=user_id)
    if created_order is None: raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to reload created order")
    await sync_order_to_moysklad_safe(session, order=created_order, user=user)
    reloaded_order = await get_order_by_id(session, created_order_id, user_id=user_id)
    if reloaded_order is None: raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to load created order")
    return reloaded_order
