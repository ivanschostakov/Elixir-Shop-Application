"""Private server-to-server authentication; never accepts Telegram IDs from public clients."""
import hashlib
import hmac
import re
import time

from fastapi import HTTPException, Request
from redis.exceptions import RedisError

import config
from src.app.services.cache import get_cache_service


def signature(key: str, timestamp: str, nonce: str, method: str, path: str, body: bytes) -> str:
    payload = f"{timestamp}\n{nonce}\n{method}\n{path}\n{hashlib.sha256(body).hexdigest()}"
    return hmac.new(key.encode(), payload.encode(), hashlib.sha256).hexdigest()


async def require_bot(request: Request):
    key = config.TELEGRAM_AI_BRIDGE_SECRET
    if not config.TELEGRAM_AI_BRIDGE_ENABLED or len(key) < 32:
        raise HTTPException(503, "Telegram integration is unavailable")
    timestamp = request.headers.get("x-elixir-timestamp", "")
    nonce = request.headers.get("x-elixir-nonce", "")
    received = request.headers.get("x-elixir-signature", "")
    try:
        valid_time = abs(time.time() - int(timestamp)) <= 90
    except ValueError:
        valid_time = False
    if not valid_time or not re.fullmatch(r"[a-f0-9]{32}", nonce):
        raise HTTPException(401, "Invalid bot authentication")
    body = await request.body()
    if len(body) > 28_000_000:
        raise HTTPException(413, "Request is too large")
    expected = signature(key, timestamp, nonce, request.method, request.url.path, body)
    if not hmac.compare_digest(received, expected):
        raise HTTPException(401, "Invalid bot authentication")
    cache = get_cache_service().client
    if cache is None:
        raise HTTPException(503, "Authentication temporarily unavailable")
    try:
        if not await cache.set(f"telegram-ai:nonce:{nonce}", "1", nx=True, ex=180):
            raise HTTPException(401, "Request already used")
    except RedisError as error:
        raise HTTPException(503, "Authentication temporarily unavailable") from error
