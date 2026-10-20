import hashlib
import hmac
import json
import time
from typing import Any
from urllib.parse import urlsplit

import httpx

from config import WEBSITE_CATALOG_PUBLIC_BASE_URL, WEBSITE_CATALOG_SYNC_ENDPOINT, WEBSITE_CATALOG_SYNC_SECRET, WEBSITE_CATALOG_SYNC_TIMEOUT_SECONDS


def website_catalog_sync_configured() -> bool:
    return bool(WEBSITE_CATALOG_SYNC_ENDPOINT and WEBSITE_CATALOG_SYNC_SECRET)


class WebsiteCatalogSyncClient:
    def __init__(self, *, endpoint: str | None = WEBSITE_CATALOG_SYNC_ENDPOINT, secret: str | None = WEBSITE_CATALOG_SYNC_SECRET, public_base_url: str | None = WEBSITE_CATALOG_PUBLIC_BASE_URL, timeout: int = WEBSITE_CATALOG_SYNC_TIMEOUT_SECONDS, transport: httpx.AsyncBaseTransport | None = None) -> None:
        if not endpoint or not secret: raise RuntimeError("Website catalog sync is not configured")
        parsed_endpoint = urlsplit(endpoint)
        if (parsed_endpoint.scheme != "https" or parsed_endpoint.hostname is None or parsed_endpoint.username is not None or parsed_endpoint.password is not None): raise RuntimeError("Website catalog sync endpoint must be an HTTPS URL without credentials")
        derived_public_base_url = (public_base_url or f"{parsed_endpoint.scheme}://{parsed_endpoint.hostname}")
        parsed_public_base_url = urlsplit(derived_public_base_url)
        if (parsed_public_base_url.scheme != "https" or parsed_public_base_url.hostname is None or parsed_public_base_url.username is not None or parsed_public_base_url.password is not None or parsed_public_base_url.path not in ("", "/") or parsed_public_base_url.query or parsed_public_base_url.fragment): raise RuntimeError("Website catalog public base URL must be an HTTPS origin")
        if len(secret) < 32: raise RuntimeError("Website catalog sync secret must contain at least 32 characters")
        self.endpoint = endpoint
        self.public_base_url = (f"{parsed_public_base_url.scheme}://{parsed_public_base_url.netloc}/")
        self.secret = secret.encode("utf-8")
        self.timeout = timeout
        self.transport = transport

    async def pull(self) -> dict[str, Any]:
        body = json.dumps({"action": "pull"}, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        timestamp = str(int(time.time()))
        signature = hmac.new(self.secret, timestamp.encode("ascii") + b"." + body, hashlib.sha256).hexdigest()
        async with httpx.AsyncClient(timeout=self.timeout, transport=self.transport) as client:
            response = await client.post(self.endpoint, content=body, headers={
                "Content-Type": "application/json",
                "X-Elixir-Timestamp": timestamp,
                "X-Elixir-Signature": signature,
            })
        response.raise_for_status()
        result = response.json()
        if not isinstance(result, dict) or result.get("ok") is not True: raise RuntimeError(str(result.get("error") if isinstance(result, dict) else "Invalid catalog sync response"))
        return result
