from __future__ import annotations

import hashlib
import hmac
import json
import time
from typing import Any

import httpx

from config import (
    BITRIX_DELIVERY_ENDPOINT,
    BITRIX_DELIVERY_SECRET,
    BITRIX_DELIVERY_TIMEOUT_SECONDS,
)


class BitrixDeliveryError(RuntimeError):
    def __init__(
        self,
        *,
        status_code: int,
        code: str,
        message_ru: str,
        message_en: str,
    ) -> None:
        super().__init__(message_ru)
        self.status_code = status_code
        self.code = code
        self.message_ru = message_ru
        self.message_en = message_en


def bitrix_delivery_configured() -> bool:
    return bool(BITRIX_DELIVERY_ENDPOINT and BITRIX_DELIVERY_SECRET and len(BITRIX_DELIVERY_SECRET) >= 32)


class BitrixDeliveryClient:
    def __init__(
        self,
        *,
        endpoint: str | None = None,
        secret: str | None = None,
        timeout_seconds: int | None = None,
    ) -> None:
        self.endpoint = str(endpoint if endpoint is not None else BITRIX_DELIVERY_ENDPOINT or "").strip()
        self.secret = str(secret if secret is not None else BITRIX_DELIVERY_SECRET or "").strip()
        self.timeout_seconds = timeout_seconds or BITRIX_DELIVERY_TIMEOUT_SECONDS
        if not self.endpoint or len(self.secret) < 32:
            raise RuntimeError("Bitrix delivery integration is not configured")

    async def quote(
        self,
        *,
        mode: str,
        destination: dict[str, Any],
        items: list[dict[str, Any]],
        user_email: str | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "action": "quote",
            "mode": mode,
            "destination": destination,
            "items": items,
        }
        if user_email:
            payload["user_email"] = user_email
        return await self._request(payload)

    async def _request(self, payload: dict[str, Any]) -> dict[str, Any]:
        timestamp = str(int(time.time()))
        body = json.dumps(
            payload,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
        signature = hmac.new(
            self.secret.encode("utf-8"),
            timestamp.encode("ascii") + b"." + body,
            hashlib.sha256,
        ).hexdigest()
        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                response = await client.post(
                    self.endpoint,
                    content=body,
                    headers={
                        "X-Elixir-Timestamp": timestamp,
                        "X-Elixir-Signature": signature,
                        "Content-Type": "application/json",
                        "Accept": "application/json",
                    },
                )
        except httpx.HTTPError as exception:
            raise BitrixDeliveryError(
                status_code=502,
                code="bitrix_unavailable",
                message_ru="Сервис расчёта доставки Bitrix временно недоступен.",
                message_en="The Bitrix delivery calculation service is temporarily unavailable.",
            ) from exception

        try:
            result = response.json()
        except ValueError as exception:
            raise BitrixDeliveryError(
                status_code=502,
                code="invalid_response",
                message_ru="Bitrix вернул некорректный ответ расчёта доставки.",
                message_en="Bitrix returned an invalid delivery calculation response.",
            ) from exception

        if response.is_success and isinstance(result, dict) and result.get("ok") is True:
            data = result.get("data")
            if isinstance(data, dict):
                return data

        if not isinstance(result, dict):
            result = {}
        raise BitrixDeliveryError(
            status_code=response.status_code if 400 <= response.status_code < 600 else 502,
            code=str(result.get("error") or "request_failed"),
            message_ru=str(result.get("message_ru") or "Не удалось рассчитать доставку в Bitrix."),
            message_en=str(result.get("message_en") or "Unable to calculate delivery in Bitrix."),
        )
