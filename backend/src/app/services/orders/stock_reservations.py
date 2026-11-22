"""Local holds cover the gap until the same reservation reaches MoySklad."""
from datetime import datetime, timedelta, timezone
import logging
from sqlalchemy import select
from fastapi import HTTPException
from src.database.models import Variant

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

async def acknowledge_remote_reservation(db, order):
    hold = (order.checkout_snapshot or {}).get("stock_reservation") or {}
    if hold.get("status") != "held": return
    quantities = hold["quantities"]
    rows = await _locked_variants(db, quantities)
    for row in rows:
        row.local_reserved = max(0, (row.local_reserved or 0) - quantities[str(row.id)])
        row.stock_valid_after = datetime.now(timezone.utc)
    order.checkout_snapshot = dict(order.checkout_snapshot, stock_reservation={**hold, "status": "exported"})
    await db.commit()

async def release_local_reservation(db, order):
    hold = (order.checkout_snapshot or {}).get("stock_reservation") or {}
    if hold.get("status") not in {"held", "exported"} or order.is_paid or order.is_shipped: return
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
    from src.database.models import Order
    async with SessionLocal() as db:
        rows = (await db.execute(select(Order).where(Order.is_paid.is_(False),
            Order.checkout_snapshot["stock_reservation"]["status"].astext.in_(["held", "exported"]),
        ).order_by(Order.id).with_for_update(skip_locked=True).limit(100))).scalars().all()
        now = datetime.now(timezone.utc)
        for order in rows:
            hold = order.checkout_snapshot["stock_reservation"]
            if datetime.fromisoformat(hold["expires_at"]) <= now:
                if order.payment_invoice_id and order.payment_status not in {"canceled", "error"}: continue
                # Manager payment can arrive through another channel. Its remote
                # reservation is released only after a confirmed cancellation.
                if order.moysklad_customerorder_id and order.payment_method == "later" and not order.is_canceled:
                    continue
                try:
                    await release_local_reservation(db, order)
                    order.is_canceled = True
                    order.payment_status = "canceled"
                    from .payment_effects import queue_payment_effects
                    await queue_payment_effects(db, order)
                except Exception:
                    log.exception("Stock reservation release deferred order_id=%s", order.id)
                    continue
        await db.commit()
