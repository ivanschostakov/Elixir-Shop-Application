"""Event-driven loyalty milestones. Only an explicit acceptance changes program."""
from decimal import Decimal

import httpx
from fastapi import HTTPException
from sqlalchemy import select

from config import LOYALTY_COMPANY_PROMO_CODE, LOYALTY_USE_SETTLEMENT_BALANCE
from src.app.services.benefits.settlement import (
    OWN_PROMO_ATTRIBUTE_ID, PROGRAM_ATTRIBUTE_ID, PROGRAM_NAMES, REFERRER_ATTRIBUTE_ID,
    DISCOUNT_ATTRIBUTE_ID, get_account_settlement,
)
from src.app.services.benefits.settlement_cache import invalidate_account_settlement
from src.app.services.orders.settlement_payment import settlement_lock
from src.database.models import User
from src.integrations.moysklad.client import get_moysklad_client
from .calculations import MIN_PERSONAL_DISCOUNT_SPEND, PARTNER_UNLOCK_SPEND
from .ms_codes import find_ms_code_owners, milestone_code
from .order_attribution import lock_order_referrer, require_no_competing_referral
from .registration import _attribute_builder


def _result(program, total, own, incoming):
    company = (LOYALTY_COMPANY_PROMO_CODE or "").strip()
    offer = bool(company and program == 1 and total >= MIN_PERSONAL_DISCOUNT_SPEND
                 and (not incoming or incoming.casefold() == company.casefold()))
    return {"offer_partner": offer, "own_promo_code": own or None,
            "company_promo_code": company if offer else None, "own_code_eligible": total >= PARTNER_UNLOCK_SPEND}


def _card(card, cid):
    if not card or str(card.get("id")) != str(cid) or card.get("archived"):
        raise ValueError("Wrong or archived counterparty")
    attrs = {a["id"]: a.get("value") for a in card.get("attributes", [])}
    program = PROGRAM_NAMES.get(str((attrs.get(PROGRAM_ATTRIBUTE_ID) or {}).get("name", "")).strip().casefold())
    minor = Decimal(str(card["salesAmount"]))
    if program is None or not minor.is_finite() or minor < 0 or minor != minor.to_integral_value():
        raise ValueError("Unverified program or purchase total")
    discount = attrs.get(DISCOUNT_ATTRIBUTE_ID)
    if isinstance(discount, dict):
        discount = discount["name"]
    rate = Decimal(str(discount or 0).strip().removesuffix("%").strip().replace(",", "."))
    if not rate.is_finite() or not 0 <= rate <= 100:
        raise ValueError("Unverified accounting discount")
    return (program, minor / 100, (attrs.get(OWN_PROMO_ATTRIBUTE_ID) or "").strip(),
            (attrs.get(REFERRER_ATTRIBUTE_ID) or "").strip(), rate)


async def _update_locked(client, cid, *, accept):
    first = _card(await client.get_counterparty(cid), cid)
    program, total, own, incoming, rate = first
    state = _result(program, total, own, incoming)
    company = (LOYALTY_COMPANY_PROMO_CODE or "").strip()
    transition = accept and state["offer_partner"]
    if accept and not transition and not (program == 2 and company and incoming.casefold() == company.casefold()):
        raise HTTPException(409, "Условия программы изменились. Обновите профиль.")
    issue = state["own_code_eligible"] and not own
    if not transition and not issue:
        return state
    attribute = await _attribute_builder(client)
    patch = []
    if transition:
        if await find_ms_code_owners(company, client):
            raise HTTPException(409, "Код компании совпадает с личным промокодом. Обратитесь в поддержку.")
        if rate > 20:
            raise HTTPException(409, "У клиента особые условия скидки. Обратитесь в поддержку.")
        patch.extend([await attribute(PROGRAM_ATTRIBUTE_ID, code=2),
                      await attribute(REFERRER_ATTRIBUTE_ID, text=company),
                      await attribute(DISCOUNT_ATTRIBUTE_ID, number=max(Decimal(3), rate))])
    new_code = milestone_code(cid) if issue else own
    if issue:
        if new_code.casefold() == company.casefold() or await find_ms_code_owners(new_code, client):
            raise HTTPException(409, "Не удалось однозначно назначить личный промокод.")
        patch.append(await attribute(OWN_PROMO_ATTRIBUTE_ID, text=new_code))
    if _card(await client.get_counterparty(cid), cid) != first:
        raise HTTPException(409, "Карточка обновилась. Повторите проверку.")
    try:
        await client._update_entity("counterparty", cid, {"attributes": patch})
        p, spend, actual, ref, actual_rate = _card(await client.get_counterparty(cid), cid)
        if (actual != new_code or p != (2 if transition else program)
                or ref != (company if transition else incoming)
                or actual_rate != (max(Decimal(3), rate) if transition else rate)):
            raise ValueError("Loyalty update was not confirmed")
        return _result(p, spend, actual, ref)
    finally:
        await invalidate_account_settlement(cid)


async def check_milestones(db, *, user, accept=False):
    cid = user.moysklad_counterparty_id
    if not user.is_verified or not cid or not LOYALTY_USE_SETTLEMENT_BALANCE:
        if accept:
            raise HTTPException(409, "Для смены программы нужен подтверждённый профиль МойСклад.")
        return _result(None, 0, None, None)
    if not accept:
        view = await get_account_settlement(cid)
        if view.status != "fresh" or view.total_purchases_rubles is None or view.loyalty_program not in (0, 1, 2):
            raise HTTPException(503, "Не удалось проверить покупки в МойСклад. Повторите позже.")
        state = _result(view.loyalty_program, view.total_purchases_rubles, view.own_promo_code, view.referrer_promo_code)
        if not state["own_code_eligible"] or state["own_promo_code"]:
            return state
    async with settlement_lock(cid):
        linked = (await db.scalars(select(User.id).where(User.moysklad_counterparty_id == cid).limit(2))).all()
        if linked != [user.id]:
            raise HTTPException(409, "Нужна сверка привязки карточки МойСклад.")
        if accept:
            await lock_order_referrer(db, cid)
            await require_no_competing_referral(db, cid, LOYALTY_COMPANY_PROMO_CODE or "")
        try:
            return await _update_locked(get_moysklad_client(), cid, accept=accept)
        except (ValueError, TypeError, KeyError, RuntimeError, AttributeError, ArithmeticError, httpx.HTTPError) as exc:
            raise HTTPException(503, "МойСклад не подтвердил изменение. Обновите профиль.") from exc
