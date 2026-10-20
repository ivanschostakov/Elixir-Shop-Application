from datetime import datetime, timedelta, timezone
from copy import deepcopy
from decimal import Decimal
from typing import Any
from fastapi.encoders import jsonable_encoder
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from config import MOY_SKLAD_ORDER_SYNC_ENABLED
from src.database.models import IntegrationRun, Order, User
from src.normalize import coerce_uuid
from src.integrations.moysklad.client import get_moysklad_client
from src.integrations.moysklad.idempotency import build_counterparty_external_code, build_customerorder_external_code, build_sync_id
from src.integrations.moysklad.schemas import MoySkladOrderSyncResult, MoySkladCounterpartySyncResult
from src.integrations.moysklad.settlement_checkout import order_settlement, entity_id
from .common import log
from .contacts import _counterparty_address, _counterparty_email, _counterparty_phone, _full_name
from .organization import _resolve_organization_id
from .positions import _build_customerorder_positions, _load_assortment_refs
from .description import _build_order_description
from .address import _shipment_address, _shipment_address_full
from .attributes import _invoiceout_external_code, _invoiceout_name, _is_intellectmoney_payment, _moysklad_attr_values, _moysklad_custom_attr_refs, _resolve_customerorder_refs


async def sync_order_to_moysklad(session: AsyncSession, *, order: Order, user: User) -> MoySkladOrderSyncResult:
    if not MOY_SKLAD_ORDER_SYNC_ENABLED: return MoySkladOrderSyncResult(enabled=False, skipped_reason="disabled")

    moysklad_client = get_moysklad_client()
    if not moysklad_client.is_configured(): return MoySkladOrderSyncResult(enabled=True, skipped_reason="client_not_configured")
    if not order.items: return MoySkladOrderSyncResult(enabled=True, skipped_reason="empty_order")

    organization_id = await _resolve_organization_id(moysklad_client)
    if organization_id is None: return MoySkladOrderSyncResult(enabled=True, skipped_reason="organization_not_found")

    user_id = int(user.__dict__.get("id") or user.id)
    counterparty_external_code = build_counterparty_external_code(user_id=user_id)
    counterparty_sync_id = build_sync_id(scope="counterparty", key=counterparty_external_code)
    settlement = order_settlement(order)
    if settlement:
        expected_id = coerce_uuid(settlement.get("counterparty_id"))
        if expected_id is None or user.moysklad_counterparty_id != expected_id: raise ValueError("Settlement counterparty changed; refuse to relink funds")
        counterparty = await moysklad_client.get_counterparty(expected_id)
        if not counterparty or counterparty.get("archived") or entity_id(counterparty) != expected_id: raise ValueError("Settlement counterparty is unavailable")
        counterparty_result = MoySkladCounterpartySyncResult(expected_id, counterparty_external_code)
        snapshot = deepcopy(order.checkout_snapshot)
        snapshot["settlement_payment"]["organization_id"] = str(organization_id)
        order.checkout_snapshot = snapshot
        await session.commit()
    else: counterparty_result = await moysklad_client.resolve_or_sync_counterparty(existing_counterparty_id=user.moysklad_counterparty_id, external_code=counterparty_external_code, sync_id=counterparty_sync_id, name=_full_name(user, order), email=_counterparty_email(user, order), phone=_counterparty_phone(user, order), actual_address=_counterparty_address(order),)

    if user.moysklad_counterparty_id != counterparty_result.counterparty_id:
        user.moysklad_counterparty_id = counterparty_result.counterparty_id
        await session.flush()
        await session.commit()

    await session.execute(select(Order.id).where(Order.id == order.id).with_for_update())
    await session.refresh(order, attribute_names=["moysklad_customerorder_id", "moysklad_invoiceout_id"])
    variant_ids = [int(item.variant_id) for item in order.items]
    assortment_refs = await _load_assortment_refs(session, variant_ids=variant_ids)
    positions, missing_variant_ids = _build_customerorder_positions(moysklad_client=moysklad_client, assortment_refs=assortment_refs, order=order,)

    if missing_variant_ids:
        unique_missing = sorted(set(missing_variant_ids))
        log.warning("Skipping MoySklad order sync because assortment refs are missing for variants=%s order_id=%s", unique_missing, order.id)
        return MoySkladOrderSyncResult(enabled=True, skipped_reason="missing_assortment_refs", counterparty=counterparty_result,)

    if not positions: return MoySkladOrderSyncResult(
        enabled=True,
        skipped_reason="empty_positions",
        counterparty=counterparty_result,
    )

    if settlement and Decimal(order.delivery_total) > 0:
        delivery_services = await moysklad_client.get_all("/entity/service", filter="name=Доставка заказа;archived=false")
        if len(delivery_services) != 1 or entity_id(delivery_services[0]) is None: raise ValueError("A unique delivery service is required for settlement checkout")
        positions.append(moysklad_client.build_customerorder_position(assortment_entity_type="service", assortment_id=entity_id(delivery_services[0]), quantity=1, unit_price=Decimal(order.delivery_total), discount=Decimal("0")))

    customerorder_external_code = build_customerorder_external_code(order_id=order.id)
    customerorder_sync_id = build_sync_id(scope="customerorder", key=customerorder_external_code)
    refs = await _resolve_customerorder_refs(moysklad_client, order)
    if refs["store"] is None: return MoySkladOrderSyncResult(enabled=True, skipped_reason="store_not_configured", counterparty=counterparty_result)
    if refs["state"] is None: return MoySkladOrderSyncResult(enabled=True, skipped_reason="state_not_configured", counterparty=counterparty_result)
    if refs["sales_channel"] is None: return MoySkladOrderSyncResult(enabled=True, skipped_reason="sales_channel_not_configured", counterparty=counterparty_result)
    attributes = moysklad_client.build_customerorder_attributes(values=_moysklad_attr_values(order), custom_refs=await _moysklad_custom_attr_refs(moysklad_client, order))
    customerorder_result = await moysklad_client.resolve_or_sync_customerorder(existing_customerorder_id=order.moysklad_customerorder_id, external_code=customerorder_external_code, sync_id=customerorder_sync_id, organization_id=organization_id, counterparty_id=counterparty_result.counterparty_id, positions=positions, moment=order.created_at, description=_build_order_description(order), shipment_address=_shipment_address(order), shipment_address_full=await _shipment_address_full(order, moysklad_client=moysklad_client), attributes=attributes, store=refs["store"], state=refs["state"], sales_channel=refs["sales_channel"],)
    if order.moysklad_customerorder_id != customerorder_result.customerorder_id:
        order.moysklad_customerorder_id = customerorder_result.customerorder_id
        await session.flush()
        await session.commit()
    invoiceout_result = None
    if _is_intellectmoney_payment(order) and not settlement:
        await session.execute(select(Order.id).where(Order.id == order.id).with_for_update())
        await session.refresh(order, attribute_names=["moysklad_invoiceout_id"])
        order_id = int(order.__dict__.get("id") or order.id)
        invoiceout_external_code = _invoiceout_external_code(order_id)
        invoiceout_sync_id = build_sync_id(scope="invoiceout", key=invoiceout_external_code)
        invoiceout_result = await moysklad_client.resolve_or_sync_invoiceout(existing_invoiceout_id=order.moysklad_invoiceout_id, external_code=invoiceout_external_code, sync_id=invoiceout_sync_id, name=_invoiceout_name(order), organization_id=organization_id, counterparty_id=counterparty_result.counterparty_id, positions=positions, customerorder_id=customerorder_result.customerorder_id, moment=order.created_at, description=_build_order_description(order), store=refs["store"], sales_channel=refs["sales_channel"],)

    needs_commit = False
    if order.moysklad_customerorder_id != customerorder_result.customerorder_id:
        order.moysklad_customerorder_id = customerorder_result.customerorder_id
        needs_commit = True
    if invoiceout_result is not None and order.moysklad_invoiceout_id != invoiceout_result.invoiceout_id:
        order.moysklad_invoiceout_id = invoiceout_result.invoiceout_id
        needs_commit = True
    if needs_commit:
        await session.flush()
        await session.commit()

    return MoySkladOrderSyncResult(enabled=True, counterparty=counterparty_result, customerorder=customerorder_result, invoiceout=invoiceout_result,)


async def sync_order_to_moysklad_safe(session: AsyncSession, *, order: Order, user: User) -> MoySkladOrderSyncResult:
    order_id = int(order.__dict__.get("id") or order.id)
    try:
        result = await sync_order_to_moysklad(session, order=order, user=user)
        if result.skipped_reason:
            if result.enabled:
                await _record_automatic_order_sync(
                    session,
                    order_id=order_id,
                    status="error",
                    error=f"MoySklad order sync skipped: {result.skipped_reason}",
                    counters=result.as_dict(),
                )
        else:
            await _record_automatic_order_sync(
                session,
                order_id=order_id,
                status="success",
                counters=result.as_dict(),
            )
        return result
    except Exception as error:
        order_id = order.__dict__.get("id")
        user_id = user.__dict__.get("id")
        requires_rollback = not session.is_active
        if requires_rollback:
            try: await session.rollback()
            except Exception: log.exception("MoySklad rollback after sync failure also failed order_id=%s user_id=%s", order_id, user_id)
        log.exception("MoySklad order sync failed order_id=%s user_id=%s rollback=%s", order_id, user_id, requires_rollback)
        try:
            await _record_automatic_order_sync(
                session,
                order_id=int(order_id or order.id),
                status="queued",
                error=str(error)[:8000] or error.__class__.__name__,
                enqueue=True,
                retry_error=error,
            )
        except Exception: log.exception("Failed to queue MoySklad order sync retry order_id=%s", order_id)
        return MoySkladOrderSyncResult(enabled=MOY_SKLAD_ORDER_SYNC_ENABLED, skipped_reason="sync_error")


async def _record_automatic_order_sync(session: AsyncSession, *, order_id: int, status: str, counters: dict[str, Any] | None = None, error: str | None = None, enqueue: bool = False, retry_error: Exception | None = None,) -> IntegrationRun:
    idempotency_key = f"order:auto:moysklad:{order_id}"
    existing = (await session.execute(select(IntegrationRun).where(IntegrationRun.idempotency_key == idempotency_key))).scalar_one_or_none()
    if existing is not None: return existing

    delay = 0
    if enqueue:
        from src.app.services.admin.jobs import retry_delay_for_error
        delay = max(60, retry_delay_for_error(retry_error, 1)) if retry_error is not None else 60
    run = IntegrationRun(provider="moysklad", operation="moysklad_order_sync", status=status, target_type="order", target_id=str(order_id), attempts=0, max_attempts=3, counters_json=jsonable_encoder(counters or {}), error=error, idempotency_key=idempotency_key, finished_at=datetime.now(timezone.utc) if status in {"success", "error"} else None, next_attempt_at=datetime.now(timezone.utc) + timedelta(seconds=delay) if enqueue else None,)
    session.add(run)
    await session.flush()
    await session.commit()
    if enqueue:
        try:
            from src.app.services.admin.jobs import enqueue_integration_run

            await enqueue_integration_run(run.id, delay_seconds=delay)
        except Exception as enqueue_error:
            run.status = "error"
            run.error = f"Failed to enqueue MoySklad retry: {enqueue_error}"[:8000]
            run.finished_at = datetime.now(timezone.utc)
            await session.commit()
            raise
    return run
