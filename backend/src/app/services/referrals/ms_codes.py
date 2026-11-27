"""Resolve the accounting owner without changing either counterparty."""
import re
from dataclasses import dataclass
from uuid import UUID

import httpx
from config import LOYALTY_COMPANY_PROMO_CODE
from fastapi import HTTPException

from src.integrations.moysklad.client import get_moysklad_client


@dataclass(frozen=True)
class ReferralOwner:
    code: str
    id: UUID | None


async def resolve_ms_referrer(code, *, buyer_id=None, client=None):
    from src.app.services.benefits.settlement import OWN_PROMO_ATTRIBUTE_ID, PROGRAM_ATTRIBUTE_ID, PROGRAM_NAMES

    code = (code or "").strip()
    if not re.fullmatch(r"[\w .-]{1,100}", code):
        raise HTTPException(422, "Недопустимый формат промокода.")
    client = client or get_moysklad_client()
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
                owners[UUID(row["id"])] = (own, PROGRAM_NAMES.get(str(program.get("name", "")).strip().casefold()))
            offset += len(rows)
            if offset >= size:
                break
    except (httpx.HTTPError, RuntimeError, ValueError, TypeError, AttributeError, KeyError) as exc:
        raise HTTPException(503, "Не удалось проверить промокод в МойСкладе. Попробуйте позже.") from exc
    if len(owners) > 1:
        raise HTTPException(409, "У промокода несколько владельцев. Обратитесь в поддержку.")
    if not owners:
        if LOYALTY_COMPANY_PROMO_CODE and code.casefold() == LOYALTY_COMPANY_PROMO_CODE.strip().casefold():
            # A configured company invitation gives the starter rate, not a payee.
            return ReferralOwner(LOYALTY_COMPANY_PROMO_CODE.strip(), None)
        raise HTTPException(422, "Партнёрский промокод не найден.")
    owner_id, (canonical, program) = next(iter(owners.items()))
    if program != 2:
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
    incoming = next((a.get("value") for a in card.get("attributes", []) if a.get("id") == REFERRER_ATTRIBUTE_ID), None)
    if incoming and incoming.strip().casefold() != code.casefold():
        raise ValueError("MoySklad buyer has another referrer; refusing export")
