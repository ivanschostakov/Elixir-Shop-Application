from fastapi import APIRouter, Depends, Query

from src.integrations.delivery.yandex import YandexDeliveryClient, get_yandex_delivery_client, YandexCalculatedDelivery
from src.integrations.delivery.schemas import DeliveryPointMarker, DeliveryPoint

yandex_router = APIRouter(prefix="/yandex", tags=["delivery", 'yandex'])

@yandex_router.get("/delivery-point-markers", response_model=list[DeliveryPointMarker])
async def yandex_get_delivery_point_markers(yandex: YandexDeliveryClient = Depends(get_yandex_delivery_client)):
    return await yandex.get_delivery_point_markers()

@yandex_router.get("/delivery-point/{code}", response_model=DeliveryPoint)
async def yandex_get_delivery_point(code: str, yandex: YandexDeliveryClient = Depends(get_yandex_delivery_client)):
    return await yandex.get_delivery_point(code)

@yandex_router.get("/calculate", response_model=YandexCalculatedDelivery)
async def yandex_calculate_delivery(
    raw_destination: str = Query(..., alias="destination"),
    yandex: YandexDeliveryClient = Depends(get_yandex_delivery_client),
): return await yandex.calculate_delivery(raw_destination)
