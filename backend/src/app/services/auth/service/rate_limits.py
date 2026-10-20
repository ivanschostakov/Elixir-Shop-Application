from fastapi import Request
from config import AUTH_RATE_LIMIT_MAX_REQUESTS, AUTH_RATE_LIMIT_WINDOW_SECONDS, AUTH_VERIFY_RATE_LIMIT_MAX_REQUESTS
from src.app.services.rate_limit import enforce_rate_limit
from .utils import _auth_limit_key


async def _apply_auth_rate_limit(request: Request, *, scope: str, principal: str | None = None, verify: bool = False) -> None:
    await enforce_rate_limit(
        request,
        scope=scope,
        limit=AUTH_VERIFY_RATE_LIMIT_MAX_REQUESTS if verify else AUTH_RATE_LIMIT_MAX_REQUESTS,
        window_seconds=AUTH_RATE_LIMIT_WINDOW_SECONDS,
        key=_auth_limit_key(request, principal),
    )
