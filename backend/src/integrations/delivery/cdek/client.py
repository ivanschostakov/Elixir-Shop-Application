import asyncio
import logging
import httpx
import time

from typing import Any
from fastapi import HTTPException

from config import (
    CDEK_ACCOUNT,
    CDEK_API_URL,
    CDEK_SECURE_PASSWORD,
    CDEK_SENDER_ADDRESS,
    CDEK_SENDER_CITY,
    CDEK_SENDER_CITY_CODE,
    CDEK_SENDER_POSTAL_CODE,
)

from src.app.services.external_errors import external_service_http_exception
from .schemas import CDEKCalculatedDelivery
from ..schemas import CountryCode, DeliveryPointMarker, DeliveryPoint, CdekDeliveryMode

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
            "city": CDEK_SENDER_CITY,
            "code": CDEK_SENDER_CITY_CODE,
            "address": CDEK_SENDER_ADDRESS,
            "country_code": "RU",
            "postal_code": CDEK_SENDER_POSTAL_CODE,
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
    def cargo(self) -> dict[str, int]: return {"length": 18, "width": 7, "height": 24, "weight": 357}

    async def aclose(self) -> None: await self._httpx_client.aclose()

    async def get_access_token(self) -> tuple[str, int]:
        resp = await self._httpx_client.post("/v2/oauth/token", params={"grant_type": "client_credentials", "client_id": self.__account, "client_secret": self.__secure_password})
        try: resp.raise_for_status()
        except httpx.HTTPError as e:
            raise external_service_http_exception(
                service="cdek",
                operation="oauth",
                public_detail="Delivery provider authentication failed",
                raw_detail={"status_code": resp.status_code, "body": resp.text},
                exc=e,
            ) from e

        data = resp.json()
        if "access_token" not in data:
            raise external_service_http_exception(
                service="cdek",
                operation="oauth_response",
                public_detail="Delivery provider authentication failed",
                raw_detail=data,
            )

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
            raise external_service_http_exception(
                service="cdek",
                operation=f"{method.upper()} {path}",
                public_detail="Delivery provider request failed",
                raw_detail={"status_code": resp.status_code, "body": resp.text},
            )

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
            raise external_service_http_exception(
                service="cdek",
                operation="get_delivery_point",
                public_detail="Delivery provider returned invalid data",
                raw_detail={
                    "path": "/v2/deliverypoints",
                    "response_type": str(type(delivery_point)),
                },
            )

        return DeliveryPoint.from_cdek_dict(delivery_point)

    async def create_order(self, order: dict[str, Any]) -> dict[str, Any]:
        response = await self._request("POST", "/v2/orders", json=order)
        if not isinstance(response, dict):
            raise external_service_http_exception(
                service="cdek",
                operation="create_order",
                public_detail="Delivery provider returned invalid order response",
                raw_detail=response,
            )
        return response

    async def get_city_code_by_coordinates(self, latitude: float, longitude: float) -> int:
        self.log.info("CDEK calculate_delivery step=resolve_city:start latitude=%s longitude=%s", latitude, longitude)
        city_candidates = await self._request("GET", "/v2/location/cities", params={
            "lat": latitude,
            "long": longitude,
            "size": 1,
            "page": 0,
        })
        self.log.info("CDEK calculate_delivery step=resolve_city:response response_type=%s candidates_count=%s", type(city_candidates).__name__, len(city_candidates) if isinstance(city_candidates, list) else None)

        if not isinstance(city_candidates, list) or not city_candidates:
            raise external_service_http_exception(
                service="cdek",
                operation="resolve_city_by_coordinates",
                public_detail="Delivery provider could not resolve destination city",
                raw_detail={"latitude": latitude, "longitude": longitude, "response": city_candidates},
            )

        city_candidate = city_candidates[0]
        city_code = city_candidate.get("code")
        self.log.info("CDEK calculate_delivery step=resolve_city:candidate city_code=%s city=%s postal_code=%s", city_code, city_candidate.get("city"), city_candidate.get("postal_code"))

        if not isinstance(city_code, int):
            raise external_service_http_exception(
                service="cdek",
                operation="resolve_city_code",
                public_detail="Delivery provider returned invalid city code",
                raw_detail={"latitude": latitude, "longitude": longitude, "response": city_candidate},
            )

        self.log.info("CDEK calculate_delivery step=resolve_city:done city_code=%s", city_code)
        return city_code

    async def calculate_delivery(self, latitude: float, longitude: float, mode: CdekDeliveryMode, *, country_code: CountryCode | None = None, postal_code: str | None = None, address: str | None = None, city: str | None = None) -> CDEKCalculatedDelivery:
        self.log.info("CDEK calculate_delivery step=start latitude=%s longitude=%s mode=%s country_code=%s postal_code=%s city=%s has_address=%s", latitude, longitude, mode, country_code, postal_code, city, bool(address))
        city_code = await self.get_city_code_by_coordinates(latitude, longitude)
        to_location: dict[str, Any] = {"code": city_code}
        if country_code:
            to_location["country_code"] = country_code
        if postal_code:
            to_location["postal_code"] = postal_code
        if city:
            to_location["city"] = city
        if mode == "door" and address:
            to_location["address"] = address
        self.log.info("CDEK calculate_delivery step=build_to_location city_code=%s country_code=%s postal_code=%s city=%s has_address=%s", to_location.get("code"), to_location.get("country_code"), to_location.get("postal_code"), to_location.get("city"), "address" in to_location)

        # Keep calculation behavior aligned with Shop-Webapp:
        # request tariff list and select the requested tariff code from the provider response.
        expected_tariff_code = self.tariff_codes[mode]
        payload = {
            "type": 2,
            "from_location": self.from_location,
            "to_location": to_location,
            "packages": [self.cargo],
        }
        self.log.info("CDEK calculate_delivery step=request_tarifflist expected_tariff_code=%s package=%s", expected_tariff_code, self.cargo)
        response = await self._request("POST", "/v2/calculator/tarifflist", json=payload)
        self.log.info("CDEK calculate_delivery step=tarifflist_response response_type=%s keys=%s", type(response).__name__, sorted(response.keys()) if isinstance(response, dict) else None)
        if not isinstance(response, dict):
            raise external_service_http_exception(
                service="cdek",
                operation="calculate_delivery",
                public_detail="Delivery provider returned invalid tariff list response",
                raw_detail=response,
            )

        raw_tariffs = response.get("tariff_codes")
        self.log.info("CDEK calculate_delivery step=parse_tariffs tariffs_type=%s tariffs_count=%s", type(raw_tariffs).__name__, len(raw_tariffs) if isinstance(raw_tariffs, list) else None)
        if not isinstance(raw_tariffs, list):
            raise external_service_http_exception(
                service="cdek",
                operation="calculate_delivery",
                public_detail="Delivery provider returned invalid tariff list payload",
                raw_detail=response,
            )

        selected_tariff: dict[str, Any] | None = None
        fallback_tariff: dict[str, Any] | None = None
        skipped_non_dict = 0
        skipped_with_errors = 0
        for index, candidate in enumerate(raw_tariffs):
            if not isinstance(candidate, dict):
                skipped_non_dict += 1
                continue
            if candidate.get("errors"):
                skipped_with_errors += 1
                self.log.info("CDEK calculate_delivery step=scan_tariffs skip_error index=%s tariff_code=%s errors=%s", index, candidate.get("tariff_code"), candidate.get("errors"))
                continue
            if fallback_tariff is None:
                fallback_tariff = candidate
                self.log.info("CDEK calculate_delivery step=scan_tariffs fallback_set index=%s tariff_code=%s delivery_sum=%s", index, candidate.get("tariff_code"), candidate.get("delivery_sum"))
            if candidate.get("tariff_code") == expected_tariff_code:
                selected_tariff = candidate
                self.log.info("CDEK calculate_delivery step=scan_tariffs expected_found index=%s tariff_code=%s delivery_sum=%s", index, candidate.get("tariff_code"), candidate.get("delivery_sum"))
                break
        self.log.info("CDEK calculate_delivery step=scan_tariffs_done scanned=%s skipped_non_dict=%s skipped_with_errors=%s selected=%s fallback=%s", len(raw_tariffs), skipped_non_dict, skipped_with_errors, bool(selected_tariff), bool(fallback_tariff))

        effective_tariff = selected_tariff or fallback_tariff
        if effective_tariff is None:
            raise external_service_http_exception(
                service="cdek",
                operation="calculate_delivery",
                public_detail="No available delivery tariffs for requested route",
                raw_detail=response,
            )
        self.log.info("CDEK calculate_delivery step=effective_tariff source=%s tariff_code=%s delivery_sum=%s period_min=%s period_max=%s", "selected" if selected_tariff else "fallback", effective_tariff.get("tariff_code"), effective_tariff.get("delivery_sum"), effective_tariff.get("period_min"), effective_tariff.get("period_max"))

        normalized_tariff = dict(effective_tariff)
        if normalized_tariff.get("weight_calc") in (None, ""):
            normalized_tariff["weight_calc"] = self.cargo["weight"]
            self.log.info("CDEK calculate_delivery step=normalize weight_calc_default_applied weight_calc=%s", normalized_tariff.get("weight_calc"))
        if normalized_tariff.get("currency") in (None, ""):
            normalized_tariff["currency"] = (
                response.get("currency")
                if isinstance(response.get("currency"), str) and response.get("currency")
                else "RUB"
            )
            self.log.info("CDEK calculate_delivery step=normalize currency_default_applied currency=%s", normalized_tariff.get("currency"))

        result = CDEKCalculatedDelivery.model_validate(normalized_tariff)
        self.log.info("CDEK calculate_delivery step=done delivery_sum=%s period_min=%s period_max=%s weight_calc=%s currency=%s", result.delivery_sum, result.period_min, result.period_max, result.weight_calc, result.currency)
        return result


cdek_client = AsyncCDEKClient()
