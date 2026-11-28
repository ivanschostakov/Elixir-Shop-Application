"""Bind the incoming referral on the accounting card, independently of an order."""
from decimal import Decimal
from datetime import datetime, timezone
from typing import NamedTuple
from uuid import UUID

import httpx
from fastapi import HTTPException
from sqlalchemy import select

from config import LOYALTY_USE_SETTLEMENT_BALANCE
from src.app.services.benefits.settlement import DISCOUNT_ATTRIBUTE_ID, PROGRAM_ATTRIBUTE_ID, REFERRER_ATTRIBUTE_ID
from src.app.services.benefits.settlement_cache import invalidate_account_settlement
from src.app.services.orders.settlement_payment import settlement_lock
from src.database.models import User
from src.integrations.moysklad.client import get_moysklad_client
from src.normalize import ms_referrer_code
from .calculations import MIN_PARTICIPANT_DISCOUNT_PERCENT
from .ms_codes import check_company_threshold, resolve_ms_referrer
from .order_attribution import lock_order_referrer, require_no_competing_referral
from .profile import get_or_create_referral_profile
from .registration import _attribute_builder
from .unlink import _card_fields


class Binding(NamedTuple):
    code: str
    owner_id: UUID | None
    rate: Decimal


async def _bind_card(db, client, cid, code):
    card = await client.get_counterparty(cid)
    initial = _card_fields(card, cid)
    attrs, _, rate, program = initial
    incoming = ms_referrer_code((attrs.get(REFERRER_ATTRIBUTE_ID) or {}).get("value"))
    if incoming and incoming.casefold() != code.casefold():
        raise HTTPException(409, "Другой промокод уже закреплён. Сначала отвяжите его в личном кабинете.")
    owner = await resolve_ms_referrer(code, buyer_id=cid, client=client)
    invited = "пришёл по промокоду"
    if incoming and program == 2 and invited in (card.get("tags") or []):
        return Binding(incoming, owner.id, rate)
    spend = card.get("salesAmount")
    check_company_threshold(code=owner.code, program=program, incoming=incoming,
                            spend=Decimal(spend) / 100 if type(spend) is int else None)
    if program == 0:
        http = await client.client()
        report = await http.get(f"/report/counterparty/{cid}", timeout=10)
        report.raise_for_status()
        data = report.json()
        if str((data.get("counterparty") or {}).get("id")) != str(cid) or data.get("balance") != 0:
            raise HTTPException(409, "Перед сменой программы нужно сверить баланс с менеджером.")
    await require_no_competing_referral(db, cid, owner.code)
    attribute = await _attribute_builder(client)
    patch = [await attribute(REFERRER_ATTRIBUTE_ID, text=owner.code)]
    if program != 2:
        patch.append(await attribute(PROGRAM_ATTRIBUTE_ID, code=2))
    if rate < MIN_PARTICIPANT_DISCOUNT_PERCENT:
        patch.append(await attribute(DISCOUNT_ATTRIBUTE_ID, number=MIN_PARTICIPANT_DISCOUNT_PERCENT))
    latest = await client.get_counterparty(cid)
    if _card_fields(latest, cid) != initial:
        raise HTTPException(409, "Карточка покупателя изменилась. Повторите проверку.")
    tags = latest.get("tags", [])
    if not isinstance(tags, list) or not all(isinstance(t, str) for t in tags):
        raise ValueError("Invalid counterparty groups")
    changes = {"attributes": patch}
    if invited not in tags:
        changes["tags"] = [*tags, invited]
    try:
        await client._update_entity("counterparty", cid, changes)
        verified = await client.get_counterparty(cid)
        after, _, new_rate, new_program = _card_fields(verified, cid)
        actual = ms_referrer_code((after.get(REFERRER_ATTRIBUTE_ID) or {}).get("value"))
        if (actual != owner.code or new_program != 2 or invited not in (verified.get("tags") or [])
                or new_rate != max(rate, MIN_PARTICIPANT_DISCOUNT_PERCENT)):
            raise ValueError("Referral binding was not confirmed")
        return Binding(actual, owner.id, new_rate)
    finally:
        await invalidate_account_settlement(cid)


async def bind_referrer(db, *, user, code):
    cid = user.moysklad_counterparty_id
    code = ms_referrer_code(code)
    if not code:
        raise HTTPException(422, "Введите действующий промокод.")
    if not user.is_verified or not cid or not LOYALTY_USE_SETTLEMENT_BALANCE:
        raise HTTPException(409, "Для привязки нужна подтверждённая карточка покупателя в МойСкладе.")
    async with settlement_lock(cid):
        await lock_order_referrer(db, cid)
        linked = (await db.scalars(select(User.id).where(User.moysklad_counterparty_id == cid)
                                   .limit(2).with_for_update())).all()
        if linked != [user.id]:
            raise HTTPException(409, "Не удалось однозначно определить карточку покупателя.")
        try:
            binding = await _bind_card(db, get_moysklad_client(), cid, code)
        except (httpx.HTTPError, RuntimeError, ValueError, KeyError, TypeError, AttributeError, ArithmeticError) as exc:
            raise HTTPException(503, "МойСклад не подтвердил привязку. Повторите с тем же кодом.") from exc
        profile = await get_or_create_referral_profile(db, user=user)
        if profile.reward_program != "partner" or profile.reward_program_selected_at is None:
            profile.reward_program_selected_at = datetime.now(timezone.utc)
        profile.reward_program = "partner"
        profile.reward_program_selection_source = "moysklad"
        profile.current_discount_percent = binding.rate
        profile.reward_program_snapshot = dict(profile.reward_program_snapshot or {},
            program_authority="moysklad", moysklad_program_code=2, moysklad_counterparty_id=str(cid),
            moysklad_referrer_promo=binding.code, moysklad_discount_percent=str(binding.rate))
        user.promo_code = binding.code
        await db.commit()
        return binding.code
