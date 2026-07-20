import logging

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

import httpx

from config import BITRIX_PROMO_API_ENDPOINT, BITRIX_PROMO_API_TIMEOUT_SECONDS, BITRIX_PROMO_API_TOKEN
from src.normalize import optional_str

logger = logging.getLogger(__name__)


class BitrixPromoIntegrationError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class BitrixPromo:
    code: str
    discount_percent: Decimal


class BitrixPromoClient:
    def __init__(
        self,
        *,
        endpoint: str | None = BITRIX_PROMO_API_ENDPOINT,
        token: str | None = BITRIX_PROMO_API_TOKEN,
        timeout_seconds: int = BITRIX_PROMO_API_TIMEOUT_SECONDS,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._endpoint = optional_str(endpoint) or ""
        self._token = optional_str(token) or ""
        self._timeout_seconds = max(1, int(timeout_seconds))
        self._transport = transport

    def is_configured(self) -> bool:
        return bool(self._endpoint)

    async def get_promo(self, code: str) -> BitrixPromo | None:
        normalized_code = optional_str(code)
        if not normalized_code:
            return None
        if not self.is_configured():
            raise BitrixPromoIntegrationError("Bitrix promo API is not configured")

        headers = {"Accept": "application/json"}
        if self._token:
            headers["X-Promo-Token"] = self._token

        try:
            async with httpx.AsyncClient(timeout=self._timeout_seconds, transport=self._transport) as client:
                response = await client.get(self._endpoint, params={"promo": normalized_code}, headers=headers)
        except httpx.HTTPError as exc:
            raise BitrixPromoIntegrationError("Bitrix promo API is unavailable") from exc

        if response.status_code == 404:
            return None
        if response.status_code != 200:
            logger.warning("Bitrix promo lookup failed status=%s body=%s", response.status_code, response.text[:500])
            raise BitrixPromoIntegrationError(f"Bitrix promo API returned HTTP {response.status_code}")

        try:
            payload = response.json()
            returned_code = optional_str(payload.get("promo")) if isinstance(payload, dict) else None
            discount_percent = Decimal(str(payload.get("discount_percent"))) if isinstance(payload, dict) else Decimal("0")
        except (ValueError, TypeError, InvalidOperation) as exc:
            raise BitrixPromoIntegrationError("Bitrix promo API returned invalid JSON") from exc

        if not isinstance(payload, dict) or payload.get("ok") is not True or not returned_code:
            raise BitrixPromoIntegrationError("Bitrix promo API returned an invalid response")
        if discount_percent <= Decimal("0") or discount_percent > Decimal("100"):
            raise BitrixPromoIntegrationError("Bitrix promo API returned an invalid discount percent")

        return BitrixPromo(code=returned_code, discount_percent=discount_percent)


bitrix_promo_client = BitrixPromoClient()
