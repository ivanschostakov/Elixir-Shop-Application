from typing import Any

import httpx

from config import BITRIX_AI_ADMIN_TIMEOUT_SECONDS, BITRIX_AI_ADMIN_TOKEN, BITRIX_AI_ADMIN_URL


class BitrixAIAdminError(RuntimeError):
    pass


def bitrix_ai_admin_configured() -> bool:
    return bool(BITRIX_AI_ADMIN_URL and BITRIX_AI_ADMIN_TOKEN)


class BitrixAIAdminClient:
    def __init__(self) -> None:
        self.base_url = (BITRIX_AI_ADMIN_URL or "").rstrip("/")

    async def request(self, method: str, path: str, *, params: dict[str, Any] | None = None, json: dict[str, Any] | None = None) -> Any:
        if not bitrix_ai_admin_configured():
            raise BitrixAIAdminError("Bitrix AI admin integration is not configured")
        try:
            async with httpx.AsyncClient(timeout=BITRIX_AI_ADMIN_TIMEOUT_SECONDS) as client:
                response = await client.request(
                    method,
                    f"{self.base_url}/{path.lstrip('/')}",
                    params=params,
                    json=json,
                    headers={"X-Webchat-Admin-Token": BITRIX_AI_ADMIN_TOKEN},
                )
                response.raise_for_status()
                return response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise BitrixAIAdminError("Bitrix AI admin backend is unavailable") from exc


bitrix_ai_admin_client = BitrixAIAdminClient()
