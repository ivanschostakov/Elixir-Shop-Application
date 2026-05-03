import hashlib
import logging
import time

from collections import deque
from threading import Lock

from fastapi import HTTPException, Request
from starlette import status

from src.app.services.cache import get_cache_service

log = logging.getLogger(__name__)

_MEMORY_LOCK = Lock()
_MEMORY_BUCKETS: dict[str, deque[float]] = {}


def client_ip_from_request(request: Request) -> str:
    for header_name in ("cf-connecting-ip", "x-real-ip", "x-forwarded-for"):
        raw_header = (request.headers.get(header_name) or "").strip()
        if not raw_header: continue
        candidate = raw_header.split(",")[0].strip()
        if candidate: return candidate

    if request.client and request.client.host: return str(request.client.host)
    return "unknown"


def _rate_limit_exception() -> HTTPException:
    return HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Too many requests. Please try again later.")


def _memory_allow(*, bucket_key: str, limit: int, window_seconds: int) -> bool:
    now = time.time()
    cutoff = now - float(window_seconds)
    with _MEMORY_LOCK:
        bucket = _MEMORY_BUCKETS.setdefault(bucket_key, deque())
        while bucket and bucket[0] <= cutoff: bucket.popleft()
        if len(bucket) >= limit: return False
        bucket.append(now)
        
    return True


async def enforce_rate_limit(request: Request, *, scope: str, limit: int, window_seconds: int, key: str | None = None) -> None:
    if limit <= 0 or window_seconds <= 0: return

    requester_key = key or client_ip_from_request(request)
    bucket_key = f"{scope}:{requester_key}"
    redis_client = get_cache_service().client
    if redis_client is not None:
        window_slot = int(time.time() // window_seconds)
        digest = hashlib.sha256(requester_key.encode("utf-8", "replace")).hexdigest()
        redis_key = f"rate_limit:{scope}:{digest}:{window_slot}"
        try:
            count = int(await redis_client.incr(redis_key))
            if count == 1: await redis_client.expire(redis_key, window_seconds)
            if count > limit: raise _rate_limit_exception()
            return
        except HTTPException: raise
        except Exception: log.exception("rate_limit_redis_error scope=%s", scope)

    if not _memory_allow(bucket_key=bucket_key, limit=limit, window_seconds=window_seconds): raise _rate_limit_exception()
