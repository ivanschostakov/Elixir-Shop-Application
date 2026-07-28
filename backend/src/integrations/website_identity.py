from __future__ import annotations

from typing import Any

import httpx

from config import (
    WEBSITE_IDENTITY_ENDPOINT,
    WEBSITE_IDENTITY_TIMEOUT_SECONDS,
    WEBSITE_IDENTITY_TOKEN,
)


class WebsiteIdentityError(RuntimeError):
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


def website_identity_configured() -> bool:
    return bool(WEBSITE_IDENTITY_ENDPOINT and len(WEBSITE_IDENTITY_TOKEN or "") >= 32)


class WebsiteIdentityClient:
    def __init__(
        self,
        *,
        endpoint: str | None = None,
        token: str | None = None,
        timeout_seconds: int | None = None,
    ) -> None:
        self.endpoint = str(endpoint if endpoint is not None else WEBSITE_IDENTITY_ENDPOINT or "").strip()
        self.token = str(token if token is not None else WEBSITE_IDENTITY_TOKEN or "").strip()
        self.timeout_seconds = timeout_seconds or WEBSITE_IDENTITY_TIMEOUT_SECONDS
        if not self.endpoint or len(self.token) < 32:
            raise RuntimeError("Website identity integration is not configured")

    async def authenticate(self, *, login: str, password: str) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            response = await client.post(
                self.endpoint,
                json={"login": login, "password": password},
                headers={
                    "X-App-Integration-Token": self.token,
                    "Accept": "application/json",
                },
            )

        try:
            result = response.json()
        except ValueError as exception:
            raise WebsiteIdentityError(
                status_code=response.status_code,
                code="invalid_response",
                message="Website identity API returned invalid JSON",
                message_ru="API профиля сайта вернул некорректный JSON.",
                message_en="Website identity API returned invalid JSON.",
            ) from exception

        if response.is_success and isinstance(result, dict) and result.get("ok") is True:
            data = result.get("data")
            if isinstance(data, dict) and isinstance(data.get("user"), dict):
                return data

        if not isinstance(result, dict):
            result = {}
        message_en = str(result.get("message_en") or result.get("message") or "Website authentication failed")
        message_ru = str(result.get("message_ru") or "Не удалось войти через профиль сайта.")
        raise WebsiteIdentityError(
            status_code=response.status_code,
            code=str(result.get("error") or "request_failed"),
            message=message_ru,
            message_ru=message_ru,
            message_en=message_en,
        )
