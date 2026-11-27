"""Confirmed unlink of the incoming MS code only; invoices and money are never modified."""
from decimal import Decimal

import httpx
from fastapi import HTTPException
from sqlalchemy import func, select
from config import LOYALTY_USE_SETTLEMENT_BALANCE
from src.app.services.benefits.settlement import (
    DISCOUNT_ATTRIBUTE_ID, OWN_PROMO_ATTRIBUTE_ID, PROGRAM_ATTRIBUTE_ID, PROGRAM_NAMES, REFERRER_ATTRIBUTE_ID,
)
from src.app.services.benefits.settlement_cache import invalidate_account_settlement
from src.app.services.orders.settlement_payment import settlement_lock
from src.database.models import Order, RewardProgramSelectionEvent as Event, User
from src.integrations.moysklad.client import get_moysklad_client
from src.integrations.moysklad.settlement_checkout import entity_id
from .profile import get_or_create_referral_profile, normalize_referral_code
from .registration import zero_discount_attribute


def _card_fields(card, cid):
    if not card or str(card.get("id")) != str(cid) or card.get("archived"):
        raise ValueError("Unexpected counterparty")
    attrs = {a["id"]: a for a in card["attributes"]}
    def value(key):
        return attrs.get(key, {}).get("value")
    raw = value(DISCOUNT_ATTRIBUTE_ID)
    rate = Decimal(str(raw.get("name") if isinstance(raw, dict) else raw or 0).strip().removesuffix("%").replace(",", "."))
    if not rate.is_finite() or not 0 <= rate <= 100:
        raise ValueError("Unknown discount")
    program = PROGRAM_NAMES.get(str((value(PROGRAM_ATTRIBUTE_ID) or {}).get("name", "")).strip().casefold())
    if program not in (0, 1, 2):
        raise ValueError("Unknown program")
    return attrs, normalize_referral_code(value(REFERRER_ATTRIBUTE_ID)), rate, program


async def _guard_open_orders(db, client, cid):
    pending = await db.scalar(select(Order.order_code).join(User, User.id == Order.user_id).where(
        User.moysklad_counterparty_id == cid, Order.is_canceled.is_(False), Order.is_shipped.is_(False),
        Order.moysklad_customerorder_id.is_(None)).limit(1))
    def block(number):
        raise HTTPException(409, f"Заказ № {number} ещё не завершён. Отвязать промокод можно после отгрузки или отмены.")
    if pending:
        block(pending)
    for offset in range(0, 2000, 100):
        page = await client.get_page("/entity/customerorder", offset=offset, limit=100, expand="state",
            filter=f"agent={client.entity_href('counterparty', cid)};applicable=true")
        rows = page["rows"]
        if not isinstance(rows, list):
            raise ValueError("Invalid order listing")
        for row in rows:
            if entity_id(row.get("agent")) != cid:
                raise ValueError("Wrong order owner")
            state = (row.get("state") or {}).get("stateType")
            if state == "Unsuccessful" or row.get("deleted"):
                continue
            if row["sum"] > 0 and row.get("shippedSum", 0) >= row["sum"]:
                continue
            if row["sum"] == 0 and state == "Successful" and row.get("demands"):
                continue
            block(row.get("name") or row["id"])
        if not page["meta"].get("nextHref") and offset + len(rows) >= page["meta"]["size"]:
            return
        if len(rows) != 100:
            raise ValueError("Incomplete order listing")
    raise HTTPException(409, "Слишком много заказов для автоматической сверки. Обратитесь в поддержку.")


async def unlink_accounting_code(db, *, user, expected_code, operation_id):
    cid = user.moysklad_counterparty_id
    code = normalize_referral_code(expected_code)
    if not LOYALTY_USE_SETTLEMENT_BALANCE or not cid or not code:
        raise HTTPException(409, "Привязка МойСклада не подтверждена. Обновите профиль.")
    client = get_moysklad_client()
    async with settlement_lock(cid):
        if await db.scalar(select(User.id).where(User.moysklad_counterparty_id == cid, User.id != user.id).limit(1)):
            raise HTTPException(409, "Карточка связана с несколькими аккаунтами. Обратитесь в поддержку.")
        try:
            await _unlink_locked(db, user, client, cid, code, str(operation_id))
        except (httpx.HTTPError, RuntimeError, KeyError, ValueError, TypeError, AttributeError, ArithmeticError) as exc:
            raise HTTPException(503, "Не удалось подтвердить отвязку в МойСкладе. Обновите профиль и повторите.") from exc
        finally:
            await invalidate_account_settlement(cid)


async def _unlink_locked(db, user, client, cid, code, op):
    query = select(Event).where(Event.user_id == user.id, Event.source == "promo_unlink",
                                Event.snapshot["buyer"].as_string() == str(cid))
    event = await db.scalar(query.where(Event.snapshot["operation"].as_string() == op).limit(1))
    if event and event.snapshot["code"] != code:
        raise HTTPException(409, "Подтвердите отвязку текущего промокода заново.")
    card = await client.get_counterparty(cid)
    attrs, incoming, rate, program = _card_fields(card, cid)
    if event and event.snapshot["done"]:
        if incoming:
            raise HTTPException(409, "Привязка изменилась. Обновите профиль.")
        return
    if not incoming and rate == 0 and DISCOUNT_ATTRIBUTE_ID in attrs and not event:
        # A mobile timeout can discard the operation id after the remote write.
        event = await db.scalar(query.where(Event.snapshot["code"].as_string() == code,
            Event.snapshot["done"].as_boolean().is_(False)).order_by(Event.id.desc()).limit(1))
    if incoming != code and not (event and incoming is None and rate == 0 and DISCOUNT_ATTRIBUTE_ID in attrs):
        raise HTTPException(409, "Привязанный промокод изменился. Обновите профиль.")
    if incoming:
        if event and event.snapshot.get("revision") != card["updated"]:
            raise HTTPException(409, "Карточка была изменена. Подтвердите операцию заново.")
        if rate and ((attrs.get(OWN_PROMO_ATTRIBUTE_ID) or {}).get("value") or program != 2):
            raise HTTPException(409, "У вашей карточки есть отдельная скидка или собственная партнёрская программа. Для отвязки обратитесь в поддержку.")
        await _guard_open_orders(db, client, cid)
        zero = await zero_discount_attribute(client)
        if not zero["meta"]["href"].endswith("/" + DISCOUNT_ATTRIBUTE_ID):
            raise ValueError("Unexpected discount attribute")
        patch = [{"meta": attrs[REFERRER_ATTRIBUTE_ID]["meta"], "value": None}, zero]
        if event is None:
            program_name = "partner" if program == 2 else "bonus"
            event = Event(user_id=user.id, previous_program=program_name, selected_program=program_name,
                source="promo_unlink", snapshot={"code": code, "buyer": str(cid), "operation": op,
                "old_rate": str(rate), "revision": card["updated"], "done": False})
            db.add(event)
            await db.commit()
        await db.execute(select(func.pg_advisory_xact_lock(func.hashtextextended(f"order-promo:{cid}", 0))))
        # Program zero does not take the outer settlement lock during checkout.
        if program == 0:
            await _guard_open_orders(db, client, cid)
        latest = _card_fields(await client.get_counterparty(cid), cid)
        if latest != (attrs, incoming, rate, program):
            raise HTTPException(409, "Условия промокода изменились. Обновите профиль.")
        await client._update_entity("counterparty", cid, {"attributes": patch})
        after, remaining, new_rate, new_program = _card_fields(await client.get_counterparty(cid), cid)
        if remaining or new_rate or new_program != program or after.get(DISCOUNT_ATTRIBUTE_ID, {}).get("value") is None:
            raise ValueError("Unlink not verified")
    profile = await get_or_create_referral_profile(db, user=user)
    user.promo_code = None
    profile.current_discount_percent = 0
    profile.reward_program_snapshot = dict(profile.reward_program_snapshot or {},
        moysklad_referrer_promo=None, moysklad_discount_percent="0")
    event.snapshot = dict(event.snapshot, done=True)
    await db.commit()
