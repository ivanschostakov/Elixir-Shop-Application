"""Read-only account view. Never use the display balance to authorize spending."""

import asyncio
import hashlib
import logging
import secrets
import time
from decimal import Decimal, InvalidOperation
from uuid import UUID

import httpx

from src.app.modules.users.me.schemas.settlement import SettlementRead
from src.app.services.cache import get_cache_service
from src.integrations.moysklad.client import get_moysklad_client

logger = logging.getLogger(__name__)
FRESH_SECONDS = 300
RETAIN_SECONDS = 7 * 86400
RETRY_SECONDS = 60
PROGRAM_ATTRIBUTE_ID = "a779beff-9d52-11f1-0a80-06b0000da6f9"
OWN_PROMO_ATTRIBUTE_ID = "10c17c18-13e8-11f1-0a80-14740012e755"
REFERRER_ATTRIBUTE_ID = "10c17b69-13e8-11f1-0a80-14740012e754"
PROGRAM_NAMES = {"нулевая": 0, "накопительная": 1, "реферальная": 2}


def _money(value: object) -> Decimal:
    if value is None or isinstance(value, bool):
        raise ValueError("Missing settlement amount")
    try:
        number = Decimal(str(value))
        if not number.is_finite():
            raise ValueError("Invalid settlement amount")
        return (number / 100).quantize(Decimal("0.01"))
    except InvalidOperation as exc:
        raise ValueError("Invalid settlement amount") from exc


def parse_settlement(counterparty: dict, report: dict, *, expected_id: UUID, now: float) -> SettlementRead:
    if str(counterparty.get("id")) != str(expected_id):
        raise ValueError("Counterparty mismatch")
    if str((report.get("counterparty") or {}).get("id")) != str(expected_id):
        raise ValueError("Report counterparty mismatch")
    attrs = {attr.get("id"): attr.get("value") for attr in counterparty.get("attributes", [])}
    program = attrs.get(PROGRAM_ATTRIBUTE_ID)
    program_name = program.get("name", "") if isinstance(program, dict) else ""
    program_code = PROGRAM_NAMES.get(str(program_name).strip().casefold())
    purchases = _money(counterparty.get("salesAmount"))
    if purchases < 0:
        raise ValueError("Negative sales amount")
    return SettlementRead(
        status="fresh",
        balance_rubles=_money(report.get("balance")),
        total_purchases_rubles=purchases,
        loyalty_program=program_code,
        own_promo_code=attrs.get(OWN_PROMO_ATTRIBUTE_ID) or None,
        referrer_promo_code=attrs.get(REFERRER_ATTRIBUTE_ID) or None,
        fetched_at=now,
        issue="program_unknown" if program_code is None else None,
    )


def _cached(raw: str | None) -> SettlementRead | None:
    try:
        value = SettlementRead.model_validate_json(raw) if raw else None
        return value if value and value.fetched_at and value.balance_rubles is not None else None
    except (ValueError, TypeError):
        return None


def _fallback(value: SettlementRead | None, issue: str) -> SettlementRead:
    if value:
        return value.model_copy(update={"status": "stale", "issue": issue})
    return SettlementRead(status="unavailable", issue=issue)


async def get_account_settlement(counterparty_id: UUID | None, *, redis=None, client=None, now: float | None = None) -> SettlementRead:
    if counterparty_id is None:
        return SettlementRead(status="unlinked", issue="counterparty_unlinked")
    client = client or get_moysklad_client()
    if not client.is_configured():
        return SettlementRead(status="unavailable", issue="integration_unconfigured")
    redis = redis if redis is not None else get_cache_service().client
    # Fail closed if coordination is unavailable: do not turn a Redis outage into
    # an unbounded burst of report requests from every API worker.
    if redis is None:
        return SettlementRead(status="unavailable", issue="cache_unavailable")
    now = time.time() if now is None else now
    scope = hashlib.sha256(client.base_url.encode()).hexdigest()[:12]
    prefix = f"ms:settlement:v1:{scope}"
    key = f"{prefix}:{counterparty_id}"
    value = None
    try:
        value = _cached(await redis.get(key))
        if value and 0 <= now - value.fetched_at.timestamp() < FRESH_SECONDS:
            return value.model_copy(update={"status": "fresh"})
        if await redis.get(f"{key}:retry"):
            return _fallback(value, "retry_later")
        if await redis.get(f"{prefix}:cooldown"):
            return _fallback(value, "rate_limited")
        token = secrets.token_hex(12)
        if not await redis.set(f"{key}:lock", token, nx=True, ex=30):
            return _fallback(value, "refresh_in_progress")
    except Exception:
        logger.warning("settlement_cache_unavailable counterparty_id=%s", counterparty_id)
        return _fallback(value, "cache_unavailable")

    try:
        # A shared gate limits all clients together, not just one customer's cache.
        if not await redis.set(f"{prefix}:gate", "1", nx=True, ex=1):
            return _fallback(value, "refresh_in_progress")
        http = await client.client()
        async with asyncio.timeout(18):
            card_response = await http.get(f"/entity/counterparty/{counterparty_id}", timeout=8)
            card_response.raise_for_status()
            report_response = await http.get(f"/report/counterparty/{counterparty_id}", timeout=8)
            report_response.raise_for_status()
        result = parse_settlement(card_response.json(), report_response.json(), expected_id=counterparty_id, now=now)
        await redis.set(key, result.model_dump_json(), ex=RETAIN_SECONDS)
        logger.info("settlement_refreshed counterparty_id=%s", counterparty_id)
        return result
    except Exception as exc:
        status = exc.response.status_code if isinstance(exc, httpx.HTTPStatusError) else None
        issue = "counterparty_missing" if status == 404 else "refresh_failed"
        delay = RETRY_SECONDS
        if status == 429:
            issue = "rate_limited"
            try:
                delay = max(RETRY_SECONDS, min(3600, int(exc.response.headers.get("Retry-After", "60"))))
            except ValueError:
                pass
        try:
            await redis.set(f"{key}:retry", "1", ex=delay)
            if status == 429:
                await redis.set(f"{prefix}:cooldown", "1", ex=delay)
        except Exception:
            pass
        logger.warning("settlement_refresh_failed counterparty_id=%s status=%s error_type=%s", counterparty_id, status, type(exc).__name__)
        return _fallback(value, issue)
    finally:
        try:
            await redis.eval(
                "if redis.call('get', KEYS[1]) == ARGV[1] then return redis.call('del', KEYS[1]) end return 0",
                1, f"{key}:lock", token,
            )
        except Exception:
            logger.warning("settlement_unlock_failed counterparty_id=%s", counterparty_id)
