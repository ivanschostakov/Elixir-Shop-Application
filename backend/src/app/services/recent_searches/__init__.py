import logging
import time

from ..cache import get_cache_service
from .constants import RECENT_SEARCHES_DEFAULT_LIMIT, RECENT_SEARCHES_MAX_ITEMS, RECENT_SEARCHES_TTL_SECONDS

logger = logging.getLogger(__name__)

def normalize_recent_search_query(query: str) -> str: return " ".join(query.strip().split()).lower()
def _recent_searches_key(user_id: int) -> str: return f"search:recent:user:{user_id}"
async def list_recent_search_queries(*, user_id: int, limit: int = RECENT_SEARCHES_DEFAULT_LIMIT) -> list[str]:
    cache = get_cache_service()
    client = cache.client
    if client is None: return []

    resolved_limit = max(1, min(int(limit), RECENT_SEARCHES_MAX_ITEMS))
    try: raw_values = await client.zrevrange(_recent_searches_key(user_id), 0, resolved_limit - 1)
    except Exception:
        logger.exception("recent_searches_list_error user_id=%s", user_id)
        return []

    return [str(value) for value in raw_values if isinstance(value, str) and value]


async def add_recent_search_query(*, user_id: int, query: str) -> None:
    normalized_query = normalize_recent_search_query(query)
    if not normalized_query: return

    cache = get_cache_service()
    client = cache.client
    if client is None: return

    key = _recent_searches_key(user_id)
    now = float(time.time())
    try:
        await client.zadd(key, {normalized_query: now})
        size = int(await client.zcard(key))
        if size > RECENT_SEARCHES_MAX_ITEMS: await client.zremrangebyrank(key, 0, size - RECENT_SEARCHES_MAX_ITEMS - 1)
        await client.expire(key, RECENT_SEARCHES_TTL_SECONDS)

    except Exception: logger.exception("recent_searches_add_error user_id=%s", user_id)


async def clear_recent_search_queries(*, user_id: int) -> None:
    cache = get_cache_service()
    client = cache.client
    if client is None:
        return

    try: await client.delete(_recent_searches_key(user_id))
    except Exception: logger.exception("recent_searches_clear_error user_id=%s", user_id)


__all__ = [
    "RECENT_SEARCHES_DEFAULT_LIMIT",
    "RECENT_SEARCHES_MAX_ITEMS",
    "add_recent_search_query",
    "clear_recent_search_queries",
    "list_recent_search_queries",
    "normalize_recent_search_query",
]
