import asyncio
import httpx

from typing import Any
from .exceptions import WebsiteIdentityError

from config import WEBSITE_IDENTITY_ENDPOINT, WEBSITE_IDENTITY_TIMEOUT_SECONDS
from src.normalize import optional_str


class WebsiteIdentityClient:
    def __init__(self, endpoint: str | None = WEBSITE_IDENTITY_ENDPOINT, timeout_seconds: int = WEBSITE_IDENTITY_TIMEOUT_SECONDS) -> None:
        self._endpoint = optional_str(endpoint) or ""
        self._timeout_seconds = timeout_seconds
        self._client: httpx.AsyncClient | None = None
        self._client_lock = asyncio.Lock()

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is not None and not self._client.is_closed: return self._client

        async with self._client_lock:
            if self._client is None or self._client.is_closed: self._client = httpx.AsyncClient(timeout=httpx.Timeout(self._timeout_seconds))
            return self._client

    async def aclose(self) -> None:
        async with self._client_lock:
            if self._client is not None and not self._client.is_closed: await self._client.aclose()
            self._client = None

    async def authenticate(self, *, login: str, password: str) -> dict[str, Any]:
        if not self._endpoint: raise WebsiteIdentityError("Website identity endpoint is not configured")
        payload = {"login": login, "password": password}

        try:
            client = await self._get_client()
            response = await client.post(self._endpoint, json=payload)
            raw_text = response.text
            try: decoded = response.json()
            except Exception as exc: raise WebsiteIdentityError(f"Website identity endpoint returned invalid JSON: {raw_text[:500]}", status_code=response.status_code) from exc
        except httpx.TimeoutException as exc: raise WebsiteIdentityError("Website identity endpoint timed out") from exc
        except httpx.HTTPError as exc: raise WebsiteIdentityError(f"Website identity request failed: {exc}") from exc

        if not isinstance(decoded, dict): raise WebsiteIdentityError("Website identity endpoint returned unexpected payload", status_code=response.status_code)

        if response.status_code >= 400 or not decoded.get("ok"):
            raise WebsiteIdentityError(
                str(decoded.get("message") or decoded.get("error") or "Website identity authentication failed"),
                status_code=response.status_code,
                error_code=optional_str(decoded.get("error")),
            )

        data = decoded.get("data")
        if not isinstance(data, dict): raise WebsiteIdentityError("Website identity endpoint returned data in unexpected format", status_code=response.status_code)
        return data

website_identity_client = WebsiteIdentityClient()
