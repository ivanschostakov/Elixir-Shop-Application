import hashlib
from datetime import datetime, timedelta, timezone
from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert
from fastapi import HTTPException

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.models import WebhookDelivery


def _normalize_optional(value: str | None, *, max_length: int) -> str | None:
    normalized = (value or "").strip()
    if not normalized: return None
    return normalized[:max_length]


def _signature_hash(signature: str | None) -> str | None:
    normalized = _normalize_optional(signature, max_length=4096)
    if normalized is None: return None
    return hashlib.sha256(normalized.encode("utf-8", "replace")).hexdigest()


def payload_digest(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


async def register_webhook_delivery(
    session: AsyncSession,
    *,
    provider: str,
    delivery_id: str | None = None,
    signature: str | None = None,
    signature_timestamp: str | None = None,
    payload_hash: str | None = None,
    commit: bool = True,
) -> bool:
    row = WebhookDelivery(provider=(provider or "").strip().lower(), delivery_id=_normalize_optional(delivery_id, max_length=255), signature_hash=_signature_hash(signature), signature_timestamp=_normalize_optional(signature_timestamp, max_length=128), payload_hash=_normalize_optional(payload_hash, max_length=64))
    session.add(row)
    try:
        if commit:
            await session.commit()
        else:
            await session.flush()
        return True
    
    except IntegrityError:
        await session.rollback()
        return False


async def claim_webhook_delivery(session, *, provider: str, event_key: str, payload: dict):
    """A verified event is retryable until its business transaction completes."""
    now = datetime.now(timezone.utc)
    await session.execute(insert(WebhookDelivery).values(provider=provider,
        delivery_id=event_key, payload_hash=event_key, payload_json=payload,
        status="received", attempts=0).on_conflict_do_nothing())
    row = (await session.execute(select(WebhookDelivery).where(
        WebhookDelivery.provider == provider, WebhookDelivery.delivery_id == event_key,
    ).with_for_update())).scalar_one()
    if row.status == "processed":
        await session.commit()
        return None
    if row.status == "processing" and row.lease_until and row.lease_until > now:
        await session.rollback()
        raise HTTPException(503, "Event is being processed; retry later")
    row.status = "processing"
    row.attempts += 1
    row.lease_until = now + timedelta(minutes=3)
    row.next_attempt_at = None
    await session.commit()
    return row.id


async def finish_webhook_delivery(session, delivery_id: int, *, error: Exception | None = None):
    # Callers roll back a failed business transaction before recording failure.
    values = dict(status="processed", lease_until=None, last_error=None, next_attempt_at=None)
    if error is not None:
        row = await session.get(WebhookDelivery, delivery_id)
        values.update(status="failed", last_error=type(error).__name__,
            next_attempt_at=datetime.now(timezone.utc) + timedelta(seconds=min(3600, 15 * 2 ** min(row.attempts, 8))))
    await session.execute(update(WebhookDelivery).where(WebhookDelivery.id == delivery_id).values(**values))
    await session.commit()
