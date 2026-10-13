"""Settlement cache helpers shared by API routes and background workers."""

import hashlib
import logging
from uuid import UUID

from src.app.services.cache import get_cache_service
from src.integrations.moysklad.client import get_moysklad_client

logger = logging.getLogger(__name__)


async def invalidate_account_settlement(counterparty_id: UUID) -> None:
    try:
        client = get_moysklad_client()
        redis = get_cache_service().client
        if redis is None:
            return
        scope = hashlib.sha256(client.base_url.encode()).hexdigest()[:12]
        key = f"ms:settlement:v1:{scope}:{counterparty_id}"
        await redis.delete(key, f"{key}:retry")
    except Exception:
        logger.warning("settlement_cache_invalidation_failed counterparty_id=%s", counterparty_id)
