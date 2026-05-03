import asyncio
import hmac
import json
import time
import httpx

from hashlib import sha256
from typing import Any

from config import BITRIX_SYNC_API_APP_KEY, BITRIX_SYNC_API_APP_SECRET, BITRIX_SYNC_API_ENDPOINT, BITRIX_SYNC_API_TIMEOUT_SECONDS
from src.normalize import optional_str
from .batch_result import BitrixSyncBatchResult
from .exceptions import BitrixSyncApiError


class BitrixSyncApiClient:
    def __init__(self, endpoint: str | None = BITRIX_SYNC_API_ENDPOINT, app_key: str | None = BITRIX_SYNC_API_APP_KEY, app_secret: str | None = BITRIX_SYNC_API_APP_SECRET, timeout_seconds: int = BITRIX_SYNC_API_TIMEOUT_SECONDS) -> None:
        self._endpoint = optional_str(endpoint) or ""
        self._app_key = optional_str(app_key) or ""
        self._app_secret = optional_str(app_secret) or ""
        self._timeout_seconds = timeout_seconds
        self._client: httpx.AsyncClient | None = None
        self._client_lock = asyncio.Lock()

    def is_configured(self) -> bool:
        return bool(self._endpoint and self._app_key and self._app_secret)

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is not None and not self._client.is_closed: return self._client

        async with self._client_lock:
            if self._client is None or self._client.is_closed: self._client = httpx.AsyncClient(timeout=httpx.Timeout(self._timeout_seconds))
            return self._client

    async def aclose(self) -> None:
        async with self._client_lock:
            if self._client is not None and not self._client.is_closed: await self._client.aclose()
            self._client = None

    @staticmethod
    def _build_body(user_ids: list[int]) -> str:
        normalized_ids = sorted({int(user_id) for user_id in user_ids if int(user_id) > 0})
        return json.dumps({"user_ids": normalized_ids}, ensure_ascii=False, separators=(",", ":"))

    def _build_signature(self, *, method: str, timestamp: str, body: str) -> str:
        payload = f"{method.upper()}\n{timestamp}\n{body}"
        return hmac.new(self._app_secret.encode("utf-8"), payload.encode("utf-8"), sha256).hexdigest()

    def _build_headers(self, *, method: str, timestamp: str, body: str) -> dict[str, str]:
        return {
            "Content-Type": "application/json",
            "X-App-Key": self._app_key,
            "X-App-Timestamp": timestamp,
            "X-App-Signature": self._build_signature(method=method, timestamp=timestamp, body=body),
        }

    @staticmethod
    def _build_timestamp() -> str:
        return str(int(time.time()))

    @staticmethod
    def _parse_batch_result(payload: dict[str, Any]) -> BitrixSyncBatchResult:
        raw_snapshots = payload.get("data")
        raw_errors = payload.get("errors")

        if raw_snapshots is None or raw_snapshots == []: raw_snapshots = {}
        if raw_errors is None: raw_errors = {}
        if not isinstance(raw_snapshots, dict): raise BitrixSyncApiError("Bitrix sync API returned data in unexpected format")
        if not isinstance(raw_errors, dict): raise BitrixSyncApiError("Bitrix sync API returned errors in unexpected format")

        snapshots: dict[int, dict[str, Any]] = {}
        errors: dict[int, str] = {}

        for raw_user_id, snapshot in raw_snapshots.items():
            try: user_id = int(raw_user_id)
            except (TypeError, ValueError): raise BitrixSyncApiError(f"Bitrix sync API returned invalid user id: {raw_user_id!r}") from None
            if not isinstance(snapshot, dict): raise BitrixSyncApiError(f"Bitrix sync API returned invalid snapshot for user {user_id}")
            snapshots[user_id] = snapshot

        for raw_user_id, error_message in raw_errors.items():
            try: user_id = int(raw_user_id)
            except (TypeError, ValueError): raise BitrixSyncApiError(f"Bitrix sync API returned invalid error user id: {raw_user_id!r}") from None
            errors[user_id] = str(error_message)

        return BitrixSyncBatchResult(snapshots=snapshots, errors=errors)

    async def fetch_snapshots(self, user_ids: list[int]) -> BitrixSyncBatchResult:
        if not self.is_configured(): raise BitrixSyncApiError("Bitrix sync API is not configured")

        method = "POST"
        timestamp = self._build_timestamp()
        body = self._build_body(user_ids)
        try:
            client = await self._get_client()
            response = await client.post(self._endpoint, content=body.encode("utf-8"), headers=self._build_headers(method=method, timestamp=timestamp, body=body))
            raw_text = response.text
            try: payload = json.loads(raw_text)
            except json.JSONDecodeError as exc: raise BitrixSyncApiError(f"Bitrix sync API returned invalid JSON: {raw_text[:500]}") from exc

        except httpx.TimeoutException as exc: raise BitrixSyncApiError("Bitrix sync API timed out") from exc
        except httpx.HTTPError as exc: raise BitrixSyncApiError(f"Bitrix sync API request failed: {exc}") from exc

        if not isinstance(payload, dict): raise BitrixSyncApiError("Bitrix sync API returned unexpected payload")
        if response.status_code >= 400 or not payload.get("ok"):
            message = payload.get("message") or payload.get("error") or "Bitrix sync API request failed"
            raise BitrixSyncApiError(str(message))

        return self._parse_batch_result(payload)


bitrix_sync_api_client = BitrixSyncApiClient()
