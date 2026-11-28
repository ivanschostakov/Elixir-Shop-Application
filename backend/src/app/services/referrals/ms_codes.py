"""Resolve the accounting owner without changing either counterparty."""
import re
from hashlib import sha256
from dataclasses import dataclass
from uuid import UUID

import httpx
from config import LOYALTY_COMPANY_PROMO_CODE
from fastapi import HTTPException
from src.app.services.benefits.settlement_schemas import ms_referrer_code

from src.integrations.moysklad.client import get_moysklad_client
from .calculations import MIN_PERSONAL_DISCOUNT_SPEND, PARTNER_UNLOCK_SPEND
from .profile import moysklad_counterparty_sales_amount_rubles


@dataclass(frozen=True)
class ReferralOwner:
    code: str
    id: UUID | None


def check_company_threshold(*, code, program, incoming, spend):
    company = (LOYALTY_COMPANY_PROMO_CODE or "").strip()
    if program != 1 or incoming or not company or company.casefold() != code.casefold():
        return
    if spend is None:
        raise HTTPException(503, "Не удалось подтвердить сумму покупок в МойСкладе.")
    if spend < MIN_PERSONAL_DISCOUNT_SPEND:
        raise HTTPException(409, "Промокод компании доступен при покупках от 30 000 ₽.")


def milestone_code(cid: UUID) -> str:
    # Stable across retries, including a timeout after the remote write.
    return "EP-" + sha256(cid.bytes).hexdigest()[:16].upper()


async def find_ms_code_owners(code, client):
    from src.app.services.benefits.settlement import OWN_PROMO_ATTRIBUTE_ID, PROGRAM_ATTRIBUTE_ID, PROGRAM_NAMES

    code = (code or "").strip()
    if not re.fullmatch(r"[\w .-]{1,100}", code):
        raise HTTPException(422, "Недопустимый формат промокода.")
    if not client.is_configured():
        raise HTTPException(503, "Не удалось проверить промокод в МойСкладе. Попробуйте позже.")
    attr = f"{client.base_url.rstrip('/')}/entity/counterparty/metadata/attributes/{OWN_PROMO_ATTRIBUTE_ID}"
    owners = {}
    offset = 0
    try:
        # '=' is case sensitive in MS. '~' is not, but also returns substrings.
        while True:
            page = await client.get_page("/entity/counterparty", limit=100, offset=offset, filter=f"{attr}~{code}")
            rows = page["rows"]
            size = int(page["meta"]["size"])
            if size > 1000 or not isinstance(rows, list) or (not rows and offset < size):
                raise ValueError("Incomplete counterparty search")
            for row in rows:
                if row.get("archived"):
                    continue
                values = {a["id"]: a.get("value") for a in row.get("attributes", [])}
                own = (values.get(OWN_PROMO_ATTRIBUTE_ID) or "").strip()
                if own.casefold() != code.casefold():
                    continue
                program = values.get(PROGRAM_ATTRIBUTE_ID) or {}
                owners[UUID(row["id"])] = (own, PROGRAM_NAMES.get(str(program.get("name", "")).strip().casefold()),
                                            moysklad_counterparty_sales_amount_rubles(row))
            offset += len(rows)
            if offset >= size:
                break
    except (httpx.HTTPError, RuntimeError, ValueError, TypeError, AttributeError, KeyError) as exc:
        raise HTTPException(503, "Не удалось проверить промокод в МойСкладе. Попробуйте позже.") from exc
    return owners


async def resolve_ms_referrer(code, *, buyer_id=None, client=None):
    code = (code or "").strip()
    owners = await find_ms_code_owners(code, client or get_moysklad_client())
    company = (LOYALTY_COMPANY_PROMO_CODE or "").strip()
    if owners and company and code.casefold() == company.casefold():
        raise HTTPException(409, "Промокод компании совпадает с личным. Обратитесь в поддержку.")
    if len(owners) > 1:
        raise HTTPException(409, "У промокода несколько владельцев. Обратитесь в поддержку.")
    if not owners:
        if LOYALTY_COMPANY_PROMO_CODE and code.casefold() == LOYALTY_COMPANY_PROMO_CODE.strip().casefold():
            # A configured company invitation gives the starter rate, not a payee.
            return ReferralOwner(LOYALTY_COMPANY_PROMO_CODE.strip(), None)
        raise HTTPException(422, "Партнёрский промокод не найден.")
    owner_id, (canonical, program, spend) = next(iter(owners.items()))
    if program != 2 and not (program in (0, 1) and (
        canonical.casefold() == milestone_code(owner_id).casefold() or spend >= PARTNER_UNLOCK_SPEND
    )):
        raise HTTPException(422, "Владелец промокода не участвует в партнёрской программе.")
    if str(owner_id) == str(buyer_id):
        raise HTTPException(422, "Свой промокод нельзя использовать для покупки.")
    return ReferralOwner(canonical, owner_id)


async def verify_referral_export(benefits, *, buyer_id, client):
    from src.app.services.benefits.settlement import REFERRER_ATTRIBUTE_ID

    code = benefits.get("ms_order_promo")
    if not code:
        return
    if str(buyer_id) != benefits.get("ms_promo_buyer_id"):
        raise ValueError("MoySklad referral buyer changed; refusing export")
    current = await resolve_ms_referrer(code, buyer_id=buyer_id, client=client)
    if (str(current.id) if current.id else None) != benefits.get("ms_referrer_id"):
        raise ValueError("MoySklad referral owner changed; refusing export")
    card = await client.get_counterparty(buyer_id)
    if not card or card.get("archived") or str(card.get("id")) != str(buyer_id):
        raise ValueError("MoySklad referral buyer unavailable")
    incoming = ms_referrer_code(next((a.get("value") for a in card.get("attributes", []) if a.get("id") == REFERRER_ATTRIBUTE_ID), None))
    if incoming and incoming.casefold() != code.casefold():
        raise ValueError("MoySklad buyer has another referrer; refusing export")
