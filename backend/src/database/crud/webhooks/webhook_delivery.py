import hashlib

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


async def register_webhook_delivery(session: AsyncSession, *, provider: str, delivery_id: str | None = None, signature: str | None = None, signature_timestamp: str | None = None, payload_hash: str | None = None) -> bool:
    row = WebhookDelivery(provider=(provider or "").strip().lower(), delivery_id=_normalize_optional(delivery_id, max_length=255), signature_hash=_signature_hash(signature), signature_timestamp=_normalize_optional(signature_timestamp, max_length=128), payload_hash=_normalize_optional(payload_hash, max_length=64))
    session.add(row)
    try:
        await session.commit()
        return True
    
    except IntegrityError:
        await session.rollback()
        return False
