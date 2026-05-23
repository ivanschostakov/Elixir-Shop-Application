from fastapi import APIRouter, Depends, Query

from config import YANDEX_DELIVERY_POINTS_ENABLED
from src.app.services.cache import build_cache_key, get_cache_service
from src.integrations.delivery.yandex import YandexDeliveryClient, get_yandex_delivery_client, YandexCalculatedDelivery
from src.integrations.delivery.schemas import DeliveryPointMarker, DeliveryPoint

yandex_router = APIRouter(prefix="/yandex", tags=["delivery", 'yandex'])
YANDEX_MARKERS_CACHE_TTL_SECONDS = 3 * 60 * 60
YANDEX_POINT_CACHE_TTL_SECONDS = 6 * 60 * 60

@yandex_router.get("/delivery-point-markers", response_model=list[DeliveryPointMarker])
async def yandex_get_delivery_point_markers(yandex: YandexDeliveryClient = Depends(get_yandex_delivery_client)):
    if not YANDEX_DELIVERY_POINTS_ENABLED: return []

    cache = get_cache_service()
    base_key = build_cache_key(route="delivery:yandex:markers", params={})
    cache_key = await cache.versioned_key("delivery_yandex", base_key)
    cached_items = await cache.get_json(cache_key, key_prefix="delivery:yandex:markers")
    if cached_items is not None: return [DeliveryPointMarker.model_validate(item) for item in cached_items]

    items = await yandex.get_delivery_point_markers()
    await cache.set_json(cache_key, [item.model_dump(mode="json") for item in items], ttl_seconds=YANDEX_MARKERS_CACHE_TTL_SECONDS, key_prefix="delivery:yandex:markers")
    return items

@yandex_router.get("/delivery-point/{code}", response_model=DeliveryPoint)
async def yandex_get_delivery_point(code: str, yandex: YandexDeliveryClient = Depends(get_yandex_delivery_client)):
    cache = get_cache_service()
    base_key = build_cache_key(route="delivery:yandex:point", params={"code": code.strip()})
    cache_key = await cache.versioned_key("delivery_yandex", base_key)
    cached_item = await cache.get_json(cache_key, key_prefix="delivery:yandex:point")
    if cached_item is not None: return DeliveryPoint.model_validate(cached_item)
    item = await yandex.get_delivery_point(code)
    await cache.set_json(cache_key, item.model_dump(mode="json"), ttl_seconds=YANDEX_POINT_CACHE_TTL_SECONDS, key_prefix="delivery:yandex:point")
    return item

@yandex_router.get("/calculate", response_model=YandexCalculatedDelivery)
async def yandex_calculate_delivery(raw_destination: str = Query(..., alias="destination"), yandex: YandexDeliveryClient = Depends(get_yandex_delivery_client)): return await yandex.calculate_delivery(raw_destination)
