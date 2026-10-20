import hashlib
import hmac
import json
import time
from typing import Any

import httpx

from config import WEBSITE_REVIEW_SYNC_ENDPOINT, WEBSITE_REVIEW_SYNC_SECRET, WEBSITE_REVIEW_SYNC_TIMEOUT_SECONDS


PAGE_SIZE = 100


def website_review_sync_configured() -> bool:
    return bool(WEBSITE_REVIEW_SYNC_ENDPOINT and WEBSITE_REVIEW_SYNC_SECRET)


class WebsiteReviewSyncClient:
    def __init__(self) -> None:
        if not website_review_sync_configured(): raise RuntimeError("Website review sync is not configured")
        self.endpoint = WEBSITE_REVIEW_SYNC_ENDPOINT
        self.secret = WEBSITE_REVIEW_SYNC_SECRET.encode("utf-8")
        self.timeout = WEBSITE_REVIEW_SYNC_TIMEOUT_SECONDS

    async def request(self, action: str, payload: dict[str, Any]) -> dict[str, Any]:
        body = json.dumps({"action": action, **payload}, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        timestamp = str(int(time.time()))
        signature = hmac.new(self.secret, timestamp.encode("ascii") + b"." + body, hashlib.sha256).hexdigest()
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(self.endpoint, content=body, headers={
                "Content-Type": "application/json",
                "X-Elixir-Timestamp": timestamp,
                "X-Elixir-Signature": signature,
            })
            
        response.raise_for_status()
        result = response.json()
        if not isinstance(result, dict) or result.get("ok") is not True: raise RuntimeError(str(result.get("error") if isinstance(result, dict) else "Invalid review sync response"))
        return result
