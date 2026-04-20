import logging
import httpx

from typing import Any
from fastapi import HTTPException

from config import YANDEX_DELIVERY_TOKEN, YANDEX_DELIVERY_BASE_URL, YANDEX_DELIVERY_WAREHOUSE_ID
from integrations.delivery.yandex.schemas.calculated_delivery import YandexCalculatedDelivery
from normalize import is_valid_uuid
from src.integrations.delivery.schemas import DeliveryPointMarker, DeliveryPoint, YandexDeliveryMode


class YandexDeliveryClient:
    def __init__(self, api_key: str | None = YANDEX_DELIVERY_TOKEN, base_url: str = YANDEX_DELIVERY_BASE_URL, warehouse_id: str = YANDEX_DELIVERY_WAREHOUSE_ID) -> None:
        self.base_url = base_url
        self.__api_key = api_key
        self.__warehouse_id = warehouse_id
        self.__logger = logging.getLogger(__name__)
        self._httpx_client = httpx.AsyncClient(timeout=20.0, base_url=self.base_url, headers={
            "Authorization": f"Bearer {self.__api_key}",
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Accept-Language": "ru",
        })

    @property
    def log(self) -> logging.Logger: return self.__logger

    @property
    def cargo(self) -> dict[str, int]: return {"dx": 25, "dy": 15, "dz": 10, "weight_gross": 100}

    @property
    def source(self) -> dict[str, str]: return {"platform_station_id": self.__warehouse_id}


    async def aclose(self) -> None: await self._httpx_client.aclose()

    async def _request(self, method: str, path: str, *, params: dict[str, Any] | None = None, json: Any | None = None) -> dict[str, Any] | list[dict[str, Any]]:
        resp = await self._httpx_client.request(
            method=method.upper(),
            url=path,
            params=params,
            json=json,
        )
        if resp.status_code >= 400:
            body = resp.text
            self.log.error("Yandex API error %s %s: %s", method, path, body)
            raise HTTPException(
                status_code=502,
                detail={
                    "service": "yandex",
                    "status_code": resp.status_code,
                    "path": path,
                    "body": body,
                },
            )

        return resp.json()

    async def get_delivery_point_markers(self) -> list[DeliveryPointMarker]:
        response = await self._request("POST", "/pickup-points/list", json={
            "geo_id": 225,
            "type": "pickup_point",
            "payment_methods": ["already_paid"]
        })
        return [DeliveryPointMarker(code=d["id"], latitude=d["position"]["latitude"], longitude=d["position"]["longitude"]) for d in response.get("points", [])]

    async def get_delivery_point(self, point_id: str) -> DeliveryPoint:
        response = await self._request("POST", "/pickup-points/list", json={
            "geo_id": 225,
            "pickup_point_ids": [point_id],
        })
        points = response.get("points")

        if not isinstance(points, list):
            raise HTTPException(
                status_code=502,
                detail={
                    "service": "yandex",
                    "path": "/pickup-points/list",
                    "error": "Unexpected pickup point response shape",
                    "body": response,
                },
            )

        if not points:
            raise HTTPException(
                status_code=404,
                detail=f"Delivery point with code '{point_id}' was not found",
            )

        return DeliveryPoint.from_yandex_dict(points[0])

    async def calculate_delivery(self, raw_destination: str) -> YandexCalculatedDelivery:
        mode: YandexDeliveryMode
        destination: dict[str, str]
        if is_valid_uuid(raw_destination):
            mode = "self_pickup"
            destination = {"platform_station_id": raw_destination}

        else:
            mode = "time_interval"
            destination = {"address": raw_destination}

        response = await self._request("POST", "/pricing-calculator", json={
            "source": self.source,
            "tariff": mode,
            "destination": destination,
            "places": [{"physical_dims": self.cargo}],
            "total_weight": self.cargo["weight_gross"],
        })
        return YandexCalculatedDelivery.model_validate(response)


yandex_delivery_client = YandexDeliveryClient()
