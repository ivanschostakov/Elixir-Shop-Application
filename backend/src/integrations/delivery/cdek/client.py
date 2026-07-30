import asyncio
import logging
import math
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
EARTH_RADIUS_KM = 6371.0088
CITY_MATCH_MAX_DISTANCE_KM = 150.0
CITY_MATCH_AMBIGUITY_MARGIN_KM = 1.0


def _distance_km(
    latitude_a: float,
    longitude_a: float,
    latitude_b: float,
    longitude_b: float,
) -> float:
    latitude_a_rad = math.radians(latitude_a)
    latitude_b_rad = math.radians(latitude_b)
    latitude_delta = math.radians(latitude_b - latitude_a)
    longitude_delta = math.radians(longitude_b - longitude_a)
    haversine = (
        math.sin(latitude_delta / 2) ** 2
        + math.cos(latitude_a_rad)
        * math.cos(latitude_b_rad)
        * math.sin(longitude_delta / 2) ** 2
    )
    haversine = min(1.0, max(0.0, haversine))
    return EARTH_RADIUS_KM * 2 * math.atan2(math.sqrt(haversine), math.sqrt(1 - haversine))

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

    async def get_delivery_point_city_code(
        self,
        delivery_point_code: str,
        *,
        country_code: CountryCode | None = None,
    ) -> int:
        normalized_code = delivery_point_code.strip()
        if not normalized_code:
            raise HTTPException(status_code=422, detail="Не выбран пункт выдачи CDEK.")

        response = await self._request("GET", "/v2/deliverypoints", params={"code": normalized_code})
        if isinstance(response, dict):
            response = [response]
        if not isinstance(response, list):
            response = []

        normalized_country_code = str(country_code or "").strip().upper()
        for point in response:
            if not isinstance(point, dict) or str(point.get("code") or "").strip() != normalized_code:
                continue
            location = point.get("location")
            if not isinstance(location, dict):
                continue
            point_country_code = str(location.get("country_code") or "").strip().upper()
            if normalized_country_code and point_country_code != normalized_country_code:
                continue
            city_code = location.get("city_code")
            if isinstance(city_code, int) and city_code > 0:
                self.log.info(
                    "CDEK pickup destination resolved point_code=%s city_code=%s city=%s",
                    normalized_code,
                    city_code,
                    location.get("city"),
                )
                return city_code

        raise HTTPException(
            status_code=422,
            detail="Пункт выдачи CDEK не найден или не относится к выбранной стране.",
        )

    async def resolve_city_code(
        self,
        *,
        latitude: float,
        longitude: float,
        city: str | None,
        postal_code: str | None,
        country_code: CountryCode | None,
    ) -> int:
        normalized_city = str(city or "").strip()
        normalized_postal_code = str(postal_code or "").strip()
        normalized_country_code = str(country_code or "").strip().upper()
        if not normalized_city or not normalized_country_code:
            raise HTTPException(
                status_code=422,
                detail="Для доставки CDEK должны быть указаны город и страна.",
            )

        params: dict[str, Any] = {
            "city": normalized_city,
            "country_codes": normalized_country_code,
            "size": 100,
            "page": 0,
        }
        if normalized_postal_code:
            params["postal_code"] = normalized_postal_code

        response = await self._request("GET", "/v2/location/cities", params=params)
        if not isinstance(response, list):
            response = []

        candidates: list[tuple[float, dict[str, Any]]] = []
        normalized_city_key = normalized_city.casefold().replace("ё", "е")
        for candidate in response:
            if not isinstance(candidate, dict):
                continue
            city_code = candidate.get("code")
            candidate_latitude = candidate.get("latitude")
            candidate_longitude = candidate.get("longitude")
            candidate_city_key = str(candidate.get("city") or "").strip().casefold().replace("ё", "е")
            candidate_country_code = str(candidate.get("country_code") or "").strip().upper()
            if (
                not isinstance(city_code, int)
                or city_code <= 0
                or candidate_city_key != normalized_city_key
                or candidate_country_code != normalized_country_code
                or not isinstance(candidate_latitude, (int, float))
                or not isinstance(candidate_longitude, (int, float))
            ):
                continue
            distance = _distance_km(
                float(latitude),
                float(longitude),
                float(candidate_latitude),
                float(candidate_longitude),
            )
            if math.isfinite(distance):
                candidates.append((distance, candidate))

        candidates.sort(key=lambda item: item[0])
        if not candidates or candidates[0][0] > CITY_MATCH_MAX_DISTANCE_KM:
            raise HTTPException(
                status_code=422,
                detail="Город не найден в CDEK. Проверьте адрес и почтовый индекс.",
            )
        if (
            len(candidates) > 1
            and candidates[1][0] - candidates[0][0] < CITY_MATCH_AMBIGUITY_MARGIN_KM
        ):
            raise HTTPException(
                status_code=422,
                detail="Найдено несколько одинаковых городов. Уточните адрес или почтовый индекс.",
            )

        selected = candidates[0][1]
        city_code = int(selected["code"])
        self.log.info(
            "CDEK door destination resolved city_code=%s city=%s region=%s country_code=%s",
            city_code,
            selected.get("city"),
            selected.get("region"),
            selected.get("country_code"),
        )
        return city_code

    async def calculate_delivery(self, latitude: float, longitude: float, mode: CdekDeliveryMode, *, country_code: CountryCode | None = None, postal_code: str | None = None, address: str | None = None, city: str | None = None) -> CDEKCalculatedDelivery:
        self.log.info("CDEK calculate_delivery step=start latitude=%s longitude=%s mode=%s country_code=%s postal_code=%s city=%s has_address=%s", latitude, longitude, mode, country_code, postal_code, city, bool(address))
        city_code = await self.resolve_city_code(
            latitude=latitude,
            longitude=longitude,
            city=city,
            postal_code=postal_code,
            country_code=country_code,
        )
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
