from decimal import Decimal
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from starlette import status
from src.app.services.benefits.money import quantize_money
from src.app.services.benefits.redemption import redeem_order_bonus_safe
from src.app.services.discounts import discountable_subtotal_for_lines
from src.app.services.delivery_quotes import calculate_authoritative_cdek_quote
from src.app.services.recommendations import record_purchase
from src.app.services.stock_visibility import get_stock_visibility_policy
from src.database.crud import create_order, delete_order_draft, get_order_by_draft_id, get_order_by_id, get_order_draft_by_id
from src.database.models import Order, User, Variant
from src.integrations.moysklad.order_sync import sync_order_to_moysklad_safe
from src.app.services.orders.common import _delivery_string, _require_recipient_phone
from src.app.services.orders.crm import ensure_order_has_amocrm_lead
from src.app.services.orders.fulfillment_payloads import normalize_address_for_cf
from src.app.services.orders.settlement_payment import serialized_settlement_checkout
from .helpers import _clear_order_draft_references, _generate_order_code, _get_or_create_self_recipient
from .delivery import _build_selected_delivery_payload
from .snapshots import _build_checkout_snapshot
from .benefits import _persist_order_benefit_applications, _resolve_checkout_benefits
from .payloads import _build_order_create_data, _build_order_item_from_draft_item


@serialized_settlement_checkout
async def create_order_from_draft_for_user(session: AsyncSession, *, user: User, draft_id: int, payment_method: str, entered_code: str | None = None, use_bonus_rubles: bool = False, reward_mode: str | None = None, client_platform: str | None = None) -> Order:
    user_id = int(user.__dict__.get("id") or user.id)
    draft = await get_order_draft_by_id(session, draft_id, user_id=user_id)
    if draft is None: raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order draft not found")

    existing_order = await get_order_by_draft_id(session, draft.id, user_id=user_id)
    if existing_order is not None:
        await _clear_order_draft_references(session, draft_id=draft.id)
        await delete_order_draft(session, draft, commit=False)
        await session.commit()

        refreshed_order = await get_order_by_id(session, existing_order.id, user_id=user_id)
        if refreshed_order is None: raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to load existing order")
        return refreshed_order

    if draft.recipient is None:
        recipient = await _get_or_create_self_recipient(session, user=user)
        draft.recipient_id = recipient.id
        draft.recipient = recipient
        await session.flush()

    if draft.delivery_address is None: raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Delivery address is required")
    if not draft.items: raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Order draft is empty")
    draft.recipient.phone = _require_recipient_phone(draft.recipient.phone)
    current_variants = list((await session.execute(select(Variant).options(selectinload(Variant.product)).where(Variant.id.in_([item.variant_id for item in draft.items])).with_for_update())).scalars().all())
    variants_by_id = {variant.id: variant for variant in current_variants}
    stock_policy = await get_stock_visibility_policy(session)
    for item in draft.items:
        variant = variants_by_id.get(item.variant_id)
        if variant is None: raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Order draft contains unavailable items")
        visible_stock = stock_policy.visible_stock(variant.stock, variant.product)
        if variant.archived or visible_stock <= 0 or item.quantity > visible_stock: raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Order draft contains unavailable items")

    if str(draft.delivery_address.provider).upper() == "CDEK":
        authoritative_quote = await calculate_authoritative_cdek_quote(session, user=user, address=draft.delivery_address, items=draft.items,)
        draft.delivery_total = Decimal(str(authoritative_quote["delivery_sum"]))
        draft.currency = str(authoritative_quote["currency"])
        draft.delivery_period_min = int(authoritative_quote["period_min"])
        draft.delivery_period_max = int(authoritative_quote["period_max"])
        draft.grand_total = draft.basket_subtotal + draft.delivery_total
        await session.flush()

    selected_delivery_service, selected_delivery_payload = await _build_selected_delivery_payload(draft)
    discountable_subtotal = await discountable_subtotal_for_lines(session, ((item.product_id, item.line_total) for item in draft.items),)
    resolved_benefits = await _resolve_checkout_benefits(
        session,
        user=user,
        subtotal=draft.basket_subtotal,
        discountable_subtotal=discountable_subtotal,
        delivery_total=draft.delivery_total,
        currency=draft.currency,
        entered_code=entered_code,
        quote_items=[
            {
                "variant_system_id": str(variants_by_id[item.variant_id].system_id),
                "product_system_id": str(variants_by_id[item.variant_id].product.system_id),
                "sku": variants_by_id[item.variant_id].sku or variants_by_id[item.variant_id].product.sku,
                "quantity": item.quantity,
            }
            for item in draft.items
        ],
        use_bonus_rubles=use_bonus_rubles,
        reward_mode=reward_mode,
    )
    grand_total = (quantize_money(resolved_benefits["cash_total"]) if resolved_benefits.get("cash_total") is not None else (quantize_money(resolved_benefits["total_after_discounts"]) or Decimal("0.00")) + draft.delivery_total)
    checkout_snapshot = _build_checkout_snapshot(draft, client_platform=client_platform, payment_method=payment_method, selected_delivery_service=selected_delivery_service, selected_delivery_payload=selected_delivery_payload, resolved_benefits=resolved_benefits,)
    delivery_string = _delivery_string(selected_delivery_service, normalize_address_for_cf(selected_delivery_payload.get("address")))

    order_code = await _generate_order_code(session)
    order_create = _build_order_create_data(user_id=user_id, delivery_address_id=draft.delivery_address_id, recipient_id=draft.recipient_id, order_code=order_code, items_count=draft.items_count, total_quantity=draft.total_quantity, basket_subtotal=draft.basket_subtotal, delivery_total=draft.delivery_total, grand_total=grand_total, currency=draft.currency, delivery_period_min=draft.delivery_period_min, delivery_period_max=draft.delivery_period_max, comment=draft.comment, delivery_string=delivery_string, selected_delivery_service=selected_delivery_service, selected_delivery_payload=selected_delivery_payload, checkout_snapshot=checkout_snapshot, payment_method=payment_method,)
    order = await create_order(session, order_create, commit=False)
    order_items = [_build_order_item_from_draft_item(user_id=user_id, order_id=order.id, item=item) for item in draft.items]
    session.add_all(order_items)
    await session.flush()
    await _persist_order_benefit_applications(session, order=order, user=user, resolved_benefits=resolved_benefits)
    for item in draft.items: await record_purchase(session, user_id=user_id, product_id=item.product_id, quantity=item.quantity, commit=False)
    await ensure_order_has_amocrm_lead(session, order, user=user)
    await _clear_order_draft_references(session, draft_id=draft.id)
    await delete_order_draft(session, draft, commit=False)
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
