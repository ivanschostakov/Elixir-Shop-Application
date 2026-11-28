"""Local holds cover the gap until the same reservation reaches MoySklad."""
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import logging
import httpx
from sqlalchemy import select, or_
from fastapi import HTTPException
from src.database.models import Variant, Order
from src.integrations.moysklad.settlement_checkout import entity_id
from .payment_attempt import PaymentDocuments, settlement_pending

log = logging.getLogger(__name__)


async def _locked_variants(db, quantities):
    return list((await db.execute(select(Variant).where(
        Variant.id.in_([int(k) for k in quantities])).order_by(Variant.id)
        .with_for_update().execution_options(populate_existing=True))).scalars().all())

async def reserve_order_stock(db, order):
    existing = (order.checkout_snapshot or {}).get("stock_reservation")
    if existing: return
    await db.refresh(order, attribute_names=["items"])
    quantities = {}
    for item in order.items:
        quantities[item.variant_id] = quantities.get(item.variant_id, 0) + item.quantity
    rows = list((await db.execute(select(Variant).where(Variant.id.in_(quantities)).order_by(Variant.id).with_for_update().execution_options(populate_existing=True))).scalars().all())
    if len(rows) != len(quantities): raise HTTPException(409, "Товар недоступен")
    for variant in rows:
        quantity = quantities[variant.id]
        if variant.archived or variant.price <= 0 or variant.stock < quantity:
            raise HTTPException(409, "Остаток изменился. Обновите корзину.")
        variant.stock -= quantity
        variant.local_reserved = (variant.local_reserved or 0) + quantity
        for item in order.items:
            if item.variant_id == variant.id: item.weight_grams = variant.weight_grams
    order.checkout_snapshot = dict(order.checkout_snapshot or {}, stock_reservation={
        "status": "held", "quantities": {str(k): v for k, v in quantities.items()},
        "expires_at": (datetime.now(timezone.utc) + timedelta(minutes=30)).isoformat(),
    })
    await db.flush()

async def acknowledge_remote_reservation(db, order, *, remote_quantities):
    await db.execute(select(Order.id).where(Order.id == order.id).with_for_update())
    await db.refresh(order, attribute_names=["checkout_snapshot"])
    hold = (order.checkout_snapshot or {}).get("stock_reservation") or {}
    if hold.get("status") != "held": return
    quantities = hold["quantities"]
    rows = await _locked_variants(db, quantities)
    for row in rows:
        row.local_reserved = max(0, (row.local_reserved or 0) - quantities[str(row.id)])
        row.stock_valid_after = datetime.now(timezone.utc)
    order.checkout_snapshot = dict(order.checkout_snapshot, stock_reservation={**hold,
        "status": "exported", "remote_quantities": remote_quantities})
    await db.commit()


def has_exported_reservation(order):
    hold = (order.checkout_snapshot or {}).get("stock_reservation") or {}
    return bool(order.moysklad_customerorder_id and hold.get("status") == "exported" and hold.get("remote_quantities"))


def require_exported_reservation(order):
    hold = (order.checkout_snapshot or {}).get("stock_reservation") or {}
    if hold.get("status") == "released":
        raise HTTPException(409, "Время резерва истекло. Проверьте остатки и оформите заказ заново.")
    if not has_exported_reservation(order):
        raise settlement_pending()


async def verify_remote_reservation(order, *, client=None, documents=None):
    hold = (order.checkout_snapshot or {}).get("stock_reservation") or {}
    if not hold:
        return  # Existing orders created before stock holds were introduced.
    if hold.get("status") != "exported" or not hold.get("remote_quantities"):
        raise HTTPException(409, "Резерв ещё не подтверждён МойСкладом. Повторите через несколько секунд.")
    documents = documents or PaymentDocuments(client)
    try:
        remote = await documents.order(order.moysklad_customerorder_id, stock=True)
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 429:
            raise settlement_pending(rate_limit=exc.response) from exc
        raise
    positions = (remote or {}).get("positions", {}).get("rows", [])
    if (not positions or ((order.checkout_snapshot or {}).get("ms_checkout_version") == 2
                          and entity_id(remote) != order.moysklad_customerorder_id)
            or len(positions) != (remote or {}).get("positions", {}).get("meta", {}).get("size", len(positions))
            or remote.get("applicable") is not True or remote.get("deleted")
            or (remote.get("state") or {}).get("stateType") == "Unsuccessful"):
        raise HTTPException(409, "Не удалось подтвердить резерв заказа. Обратитесь в поддержку.")
    actual = {}
    for position in positions:
        meta = (position.get("assortment") or {}).get("meta") or {}
        href = meta.get("href")
        actual[href] = actual.get(href, 0) + position.get("quantity", 0)
        if meta.get("type") == "service":
            continue
        stock = position.get("stock") or {}
        if (position.get("reserve", 0) < position.get("quantity", 0)
                or "quantity" not in stock or "reserve" not in stock
                or Decimal(str(stock["quantity"])) < Decimal(str(stock["reserve"]))):
            raise HTTPException(409, "Остаток или резерв изменился. Оплата не создана; обратитесь в поддержку.")
    if actual != hold["remote_quantities"]:
        raise HTTPException(409, "Состав заказа в МойСкладе изменился. Оплата не создана.")

async def release_local_reservation(db, order):
    await db.execute(select(Order.id).where(Order.id == order.id).with_for_update())
    await db.refresh(order, attribute_names=["checkout_snapshot", "is_paid", "is_shipped", "moysklad_customerorder_id"])
    hold = (order.checkout_snapshot or {}).get("stock_reservation") or {}
    if hold.get("status") not in {"held", "exported"} or order.is_paid or order.is_shipped: return
    if hold.get("remote_export_attempted") and not order.moysklad_customerorder_id:
        raise HTTPException(409, "Результат экспорта требует сверки МойСклада перед снятием резерва")
    exported = hold["status"] == "exported" or bool(order.moysklad_customerorder_id)
    if exported:
        from src.integrations.moysklad.client import get_moysklad_client
        client = get_moysklad_client()
        remote = await client.get_customer_order(order.moysklad_customerorder_id, expand=True)
        if not remote or remote.get("shippedSum", 0) > 0 or remote.get("payedSum", 0) > 0:
            raise HTTPException(409, "Отгрузка требует ручной сверки резерва")
        for ref in remote.get("invoicesOut") or []:
            from src.integrations.moysklad.settlement_checkout import entity_id
            invoice = await client.get_invoiceout(entity_id(ref))
            if not invoice or invoice.get("payedSum", 0) > 0:
                raise HTTPException(409, "Оплата требует ручной сверки резерва")
        positions = remote.get("positions", {}).get("rows", [])
        if len(positions) != remote.get("positions", {}).get("meta", {}).get("size", len(positions)):
            raise HTTPException(409, "Невозможно полностью сверить резерв")
        for position in positions:
            if position.get("reserve", 0):
                await client._update_entity(f"customerorder/{order.moysklad_customerorder_id}/positions",
                    position["id"], {"reserve": 0})
    quantities = hold["quantities"]
    rows = await _locked_variants(db, quantities)
    for row in rows:
        quantity = min(row.local_reserved or 0, quantities[str(row.id)]) if hold["status"] == "held" else 0
        row.local_reserved = max(0, (row.local_reserved or 0) - quantity)
        if exported:
            # A fresh report, rather than arithmetic on an old snapshot, restores availability.
            row.stock = 0
            row.stock_valid_after = datetime.now(timezone.utc)
        else:
            row.stock += quantity
    order.checkout_snapshot = dict(order.checkout_snapshot, stock_reservation={**hold, "status": "released"})
    await db.flush()

async def expire_local_reservations():
    from src.database import SessionLocal
    async with SessionLocal() as db:
        ids = list((await db.execute(select(Order.id).where(Order.is_paid.is_(False),
            Order.is_shipped.is_(False), Order.payment_status.not_in(["paid", "refunded"]),
            Order.checkout_snapshot["stock_reservation"]["status"].astext.in_(["held", "exported"]),
            or_(Order.is_canceled.is_(True), Order.checkout_snapshot["stock_reservation"]["expires_at"].astext <= datetime.now(timezone.utc).isoformat()),
            or_(Order.payment_invoice_id.is_(None), Order.payment_status.in_(["canceled", "error"])),
            or_(Order.moysklad_customerorder_id.is_(None), Order.payment_method != "later", Order.is_canceled.is_(True)),
            or_(Order.moysklad_customerorder_id.is_not(None), Order.checkout_snapshot["stock_reservation"]["remote_export_attempted"].as_boolean().is_not(True)),
        ).order_by(Order.id).limit(100))).scalars().all())
    for order_id in ids:
        async with SessionLocal() as db:
            order = (await db.execute(select(Order).where(Order.id == order_id,
                Order.is_paid.is_(False)).with_for_update(skip_locked=True))).scalar_one_or_none()
            if order is None:
                continue
            hold = (order.checkout_snapshot or {}).get("stock_reservation") or {}
            if hold.get("status") not in {"held", "exported"}:
                continue
            now = datetime.now(timezone.utc)
            hold = order.checkout_snapshot["stock_reservation"]
            if order.is_canceled or datetime.fromisoformat(hold["expires_at"]) <= now:
                if order.payment_invoice_id and order.payment_status not in {"canceled", "error"}: continue
                # Manager payment can arrive through another channel. Its remote
                # reservation is released only after a confirmed cancellation.
                if order.moysklad_customerorder_id and order.payment_method == "later" and not order.is_canceled:
                    continue
                if hold.get("remote_export_attempted") and not order.moysklad_customerorder_id:
                    continue
                try:
                    await release_local_reservation(db, order)
                    order.is_canceled = True
                    order.payment_status = "canceled"
                    from .payment_effects import queue_payment_effects
                    await queue_payment_effects(db, order)
                    await db.commit()
                except Exception:
                    await db.rollback()
                    log.exception("Stock reservation release deferred order_id=%s", order_id)
                    continue
