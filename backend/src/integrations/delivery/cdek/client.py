import asyncio
import logging
import httpx
import time

from decimal import Decimal
from typing import Any
from fastapi import HTTPException

from config import CDEK_SECURE_PASSWORD, CDEK_ACCOUNT, CDEK_API_URL
from .schemas import CDEKCalculatedDelivery
from src.integrations.delivery.schemas import CountryCode, DeliveryPointMarker, DeliveryPoint, CdekDeliveryMode

log = logging.getLogger(__name__)

class AsyncCDEKClient:
    def __init__(self, account: str | None = CDEK_ACCOUNT, secure_password: str | None = CDEK_SECURE_PASSWORD, base_url: str | None = CDEK_API_URL):
        if account is None or secure_password is None: raise RuntimeError("CDEK_ACCOUNT and CDEK_SECURE_PASSWORD must be set")
        if base_url is None: raise RuntimeError("CDEK_API_URL must be set")

        self.__account = account
        self.__secure_password = secure_password
        self.base_url = base_url

        self._access_token: str | None = None
        self._token_expires_at: float = 0.0
        self._token_lock = asyncio.Lock()
        self._httpx_client = httpx.AsyncClient(timeout=20.0, base_url=self.base_url, headers={"Accept": "application/json", "Content-Type": "application/json"})
        self.log = logging.getLogger(self.__class__.__name__)

    @property
    def from_location(self) -> dict[str, Any]:
        return {
            "city": "Уфа",
            "code": 256,
            "address": "ул. Революционная, 98/1 блок А",
            "country_code": "RU",
            "postal_code": 450078,
            "coords": [54.72922108153469, 55.987779811665256],
        }

    @property
    def tariff_codes(self) -> dict[CdekDeliveryMode, int]:
        return {
            "door": 137,
            "pickup": 368,
            "office": 136,
        }
    
    @property
    def cargo(self) -> dict[str, int]: return {"length": 25, "width": 10, "height": 15, "weight": 100}

    async def aclose(self) -> None: await self._httpx_client.aclose()

    async def get_access_token(self) -> tuple[str, int]:
        resp = await self._httpx_client.post("/v2/oauth/token", params={"grant_type": "client_credentials", "client_id": self.__account, "client_secret": self.__secure_password})
        try: resp.raise_for_status()
        except httpx.HTTPError as e:
            log.exception("CDEK OAuth error: %s", resp.text)
            raise HTTPException(status_code=502, detail={"service": "cdek", "stage": "oauth", "error": str(e), "body": resp.text})

        data = resp.json()
        if "access_token" not in data: raise HTTPException(status_code=500, detail="Failed to obtain CDEK token")

        token: str = data["access_token"]
        expires_in: int = int(data.get("expires_in", 3600))
        return token, expires_in

    async def _ensure_token(self) -> str:
        now = time.time()
        if self._access_token and now < self._token_expires_at - 30: return self._access_token

        async with self._token_lock:
            now = time.time()
            if self._access_token and now < self._token_expires_at - 30: return self._access_token

            token, expires_in = await self.get_access_token()
            self._access_token = token
            self._token_expires_at = now + float(expires_in)
            self.log.info("CDEK token refreshed, ttl=%s", expires_in)
            return token

    async def token_worker(self) -> None:
        while True:
            try:
                token, expires_in = await self.get_access_token()
                self._access_token = token
                self._token_expires_at = time.time() + float(expires_in)
                sleep_for = max(float(expires_in) - 30.0, 30.0)
                self.log.info("CDEK token_worker refreshed token, next in %.0fs", sleep_for)
            except asyncio.CancelledError: raise
            except Exception:
                self.log.exception("CDEK token_worker failed; retrying in 30s")
                sleep_for = 30
            await asyncio.sleep(sleep_for)

    async def _request(self, method: str, path: str, *, params: dict[str, Any] | None = None, json: Any | None = None) -> dict[str, Any] | list[dict[str, Any]]:
        token = await self._ensure_token()
        resp = await self._httpx_client.request(method=method.upper(), url=path, params=params, json=json, headers={"Authorization": f"Bearer {token}"})
        if resp.status_code >= 400:
            body = resp.text
            self.log.error("CDEK API error %s %s: %s", method, path, body)
            raise HTTPException(status_code=502, detail={"service": "cdek", "status_code": resp.status_code, "path": path, "body": body})

        return resp.json()

    async def get_delivery_point_markers(self, country_code: CountryCode | None = "RU") -> list[DeliveryPointMarker]:
        return [DeliveryPointMarker.from_dict(d) for d in await self._request("GET", "/v2/deliverypoints", params={
            "weight_min": self.cargo["weight"],
            "length": self.cargo["length"],
            "width": self.cargo["width"],
            "height": self.cargo["height"],
            "is_handout": True,
            "country_code": country_code,
        })]

    async def get_delivery_point(self, code: str) -> DeliveryPoint:
        delivery_point = await self._request("GET", "/v2/deliverypoints", params={"code": code})

        if isinstance(delivery_point, list):
            if not delivery_point:
                raise HTTPException(status_code=404, detail=f"Delivery point with code '{code}' was not found")
            delivery_point = delivery_point[0]

        if not isinstance(delivery_point, dict):
            raise HTTPException(
                status_code=502,
                detail={
                    "service": "cdek",
                    "path": "/v2/deliverypoints",
                    "error": "Unexpected delivery point response shape",
                },
            )

        return DeliveryPoint.from_cdek_dict(delivery_point)

    async def get_city_code_by_coordinates(self, latitude: float, longitude: float) -> int:
        city_candidates = await self._request("GET", "/v2/location/cities", params={
            "lat": latitude,
            "long": longitude,
            "size": 1,
            "page": 0,
        })

        if not isinstance(city_candidates, list) or not city_candidates:
            raise HTTPException(
                status_code=502,
                detail={
                    "service": "cdek",
                    "path": "/v2/location/cities",
                    "error": "No city candidates found for coordinates",
                    "latitude": latitude,
                    "longitude": longitude,
                },
            )

        city_candidate = city_candidates[0]
        city_code = city_candidate.get("code")

        if not isinstance(city_code, int):
            raise HTTPException(
                status_code=502,
                detail={
                    "service": "cdek",
                    "path": "/v2/location/cities",
                    "error": "Resolved city is missing numeric code",
                    "latitude": latitude,
                    "longitude": longitude,
                    "body": city_candidate,
                },
            )

        return city_code

    async def calculate_delivery(
        self,
        latitude: float,
        longitude: float,
        mode: CdekDeliveryMode,
        *,
        country_code: CountryCode | None = None,
        postal_code: str | None = None,
        address: str | None = None,
        city: str | None = None,
    ) -> CDEKCalculatedDelivery:
        city_code = await self.get_city_code_by_coordinates(latitude, longitude)
        to_location: dict[str, Any] = {
            "code": city_code,
            "latitude": latitude,
            "longitude": longitude,
        }

        if country_code:
            to_location["country_code"] = country_code

        if postal_code:
            to_location["postal_code"] = postal_code

        if address:
            to_location["address"] = address

        if city:
            to_location["city"] = city

        response = await self._request("POST", "/v2/calculator/tariff", json={
            "tariff_code": self.tariff_codes[mode],
            "from_location": self.from_location,
            "to_location": to_location,
            "packages": [self.cargo]
        })
        return CDEKCalculatedDelivery.model_validate(response)


cdek_client = AsyncCDEKClient()
