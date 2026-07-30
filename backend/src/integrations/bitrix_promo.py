from __future__ import annotations

from typing import Any

import httpx

from config import BITRIX_PROMO_ENDPOINT, BITRIX_PROMO_TIMEOUT_SECONDS, BITRIX_PROMO_TOKEN


class BitrixPromoError(RuntimeError):
    def __init__(
        self,
        *,
        status_code: int,
        code: str,
        message: str,
        message_ru: str | None = None,
        message_en: str | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message_ru = message_ru or message
        self.message_en = message_en or message


def bitrix_promo_configured() -> bool:
    return bool(BITRIX_PROMO_ENDPOINT and BITRIX_PROMO_TOKEN)


class BitrixPromoClient:
    def __init__(
        self,
        *,
        endpoint: str | None = None,
        token: str | None = None,
        timeout_seconds: int | None = None,
    ) -> None:
        self.endpoint = str(endpoint if endpoint is not None else BITRIX_PROMO_ENDPOINT or "").strip()
        self.token = str(token if token is not None else BITRIX_PROMO_TOKEN or "").strip()
        self.timeout_seconds = timeout_seconds or BITRIX_PROMO_TIMEOUT_SECONDS
        if not self.endpoint or len(self.token) < 32:
            raise RuntimeError("Bitrix promo integration is not configured")

    async def lookup(self, promo: str) -> dict[str, Any]:
        return await self._request({"action": "lookup", "promo": promo})

    async def quote(
        self,
        *,
        promo: str,
        items: list[dict[str, Any]],
        bitrix_user_id: int | None = None,
        user_email: str | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "action": "quote",
            "promo": promo,
            "items": items,
        }
        if bitrix_user_id is not None and bitrix_user_id > 0:
            payload["user_id"] = bitrix_user_id
        if user_email:
            payload["user_email"] = user_email
        return await self._request(payload)

    async def context(
        self,
        *,
        promo: str,
        bitrix_user_id: int | None = None,
        user_email: str | None = None,
    ) -> dict[str, Any]:
        return await self._user_request(
            action="context",
            promo=promo,
            bitrix_user_id=bitrix_user_id,
            user_email=user_email,
        )

    async def profile(
        self,
        *,
        bitrix_user_id: int | None = None,
        user_email: str | None = None,
    ) -> dict[str, Any]:
        return await self._user_request(
            action="profile",
            bitrix_user_id=bitrix_user_id,
            user_email=user_email,
        )

    async def attach_referrer(
        self,
        *,
        promo: str,
        bitrix_user_id: int | None = None,
        user_email: str | None = None,
    ) -> dict[str, Any]:
        return await self._user_request(
            action="attach_referrer",
            promo=promo,
            bitrix_user_id=bitrix_user_id,
            user_email=user_email,
        )

    async def detach_referrer(
        self,
        *,
        bitrix_user_id: int | None = None,
        user_email: str | None = None,
    ) -> dict[str, Any]:
        return await self._user_request(
            action="detach_referrer",
            bitrix_user_id=bitrix_user_id,
            user_email=user_email,
        )

    async def quote_referral_accrual(
        self,
        *,
        external_order_id: str,
        user_email: str,
        promo: str,
        amount: str,
        currency: str,
        paid_at: str,
    ) -> dict[str, Any]:
        return await self._request(
            {
                "action": "quote_referral_accrual",
                "external_order_id": external_order_id,
                "user_email": user_email,
                "promo": promo,
                "amount": amount,
                "currency": currency,
                "paid_at": paid_at,
            }
        )

    async def record_paid_purchase(
        self,
        *,
        external_order_id: str,
        user_email: str,
        promo: str,
        amount: str,
        currency: str,
        paid_at: str,
    ) -> dict[str, Any]:
        return await self._request(
            {
                "action": "record_paid_purchase",
                "external_order_id": external_order_id,
                "user_email": user_email,
                "promo": promo,
                "amount": amount,
                "currency": currency,
                "paid_at": paid_at,
            }
        )

    async def referral_eligibility(
        self,
        *,
        period: str,
        bitrix_user_id: int | None = None,
        user_email: str | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "action": "referral_eligibility",
            "period": period,
        }
        if bitrix_user_id is not None and bitrix_user_id > 0:
            payload["user_id"] = bitrix_user_id
        if user_email:
            payload["user_email"] = user_email
        return await self._request(payload)

    async def _user_request(
        self,
        *,
        action: str,
        promo: str | None = None,
        bitrix_user_id: int | None = None,
        user_email: str | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {"action": action}
        if promo:
            payload["promo"] = promo
        if bitrix_user_id is not None and bitrix_user_id > 0:
            payload["user_id"] = bitrix_user_id
        if user_email:
            payload["user_email"] = user_email
        return await self._request(payload)

    async def _request(self, payload: dict[str, Any]) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            response = await client.post(
                self.endpoint,
                json=payload,
                headers={
                    "X-Elixir-Promo-Token": self.token,
                    "Accept": "application/json",
                },
            )

        try:
            result = response.json()
        except ValueError as exception:
            raise BitrixPromoError(
                status_code=response.status_code,
                code="invalid_response",
                message="Bitrix promo API returned invalid JSON",
                message_ru="API промокодов Bitrix вернул некорректный JSON.",
                message_en="Bitrix promo API returned invalid JSON.",
            ) from exception

        if response.is_success and isinstance(result, dict) and result.get("ok") is True:
            data = result.get("data")
            if isinstance(data, dict):
                return data

        if not isinstance(result, dict):
            result = {}
        message_en = str(result.get("message_en") or result.get("message") or "Bitrix promo request failed")
        message_ru = str(result.get("message_ru") or "Не удалось проверить промокод в Bitrix.")
        raise BitrixPromoError(
            status_code=response.status_code,
            code=str(result.get("error") or "request_failed"),
            message=message_ru,
            message_ru=message_ru,
            message_en=message_en,
        )
