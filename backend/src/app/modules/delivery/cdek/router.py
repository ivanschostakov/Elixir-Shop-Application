from logging import getLogger

from fastapi import APIRouter, Depends, Query

from src.app.services.cache import build_cache_key, get_cache_service
from src.integrations.delivery.cdek import get_cdek_client, AsyncCDEKClient, CDEKCalculatedDelivery
from src.integrations.delivery.schemas import CountryCode, DeliveryPointMarker, DeliveryPoint, CdekDeliveryMode

cdek_router = APIRouter(prefix="/cdek", tags=["cdek"])
logger = getLogger(__name__)
CDEK_MARKERS_CACHE_TTL_SECONDS = 3 * 60 * 60
CDEK_POINT_CACHE_TTL_SECONDS = 6 * 60 * 60

@cdek_router.get("/delivery-point-markers", response_model=list[DeliveryPointMarker])
async def cdek_get_delivery_point_markers(country_code: CountryCode = "RU", cdek: AsyncCDEKClient = Depends(get_cdek_client)):
    cache = get_cache_service()
    base_key = build_cache_key(route="delivery:cdek:markers", params={"country_code": country_code})
    cache_key = await cache.versioned_key("delivery_cdek", base_key)
    cached_items = await cache.get_json(cache_key, key_prefix="delivery:cdek:markers")
    if cached_items is not None: return [DeliveryPointMarker.model_validate(item) for item in cached_items]
    items = await cdek.get_delivery_point_markers(country_code)
    await cache.set_json(cache_key, [item.model_dump(mode="json") for item in items], ttl_seconds=CDEK_MARKERS_CACHE_TTL_SECONDS, key_prefix="delivery:cdek:markers")
    return items

@cdek_router.get("/delivery-point/{code}", response_model=DeliveryPoint)
async def cdek_delivery_point(code: str, cdek: AsyncCDEKClient = Depends(get_cdek_client)):
    cache = get_cache_service()
    base_key = build_cache_key(route="delivery:cdek:point", params={"code": code.strip()})
    cache_key = await cache.versioned_key("delivery_cdek", base_key)
    cached_item = await cache.get_json(cache_key, key_prefix="delivery:cdek:point")
    if cached_item is not None: return DeliveryPoint.model_validate(cached_item)
    item = await cdek.get_delivery_point(code)
    await cache.set_json(cache_key, item.model_dump(mode="json"), ttl_seconds=CDEK_POINT_CACHE_TTL_SECONDS, key_prefix="delivery:cdek:point")
    return item

@cdek_router.get("/calculate", response_model=CDEKCalculatedDelivery)
async def cdek_delivery_calculate(latitude: float = Query(..., alias="latitude"), longitude: float = Query(..., alias="longitude"), mode: CdekDeliveryMode = Query(..., alias="mode"), country_code: CountryCode | None = Query(None, alias="country_code"), postal_code: str | None = Query(None, alias="postal_code"), address: str | None = Query(None, alias="address"), city: str | None = Query(None, alias="city"), cdek: AsyncCDEKClient = Depends(get_cdek_client)): return await cdek.calculate_delivery(latitude, longitude, mode, country_code=country_code, postal_code=postal_code, address=address, city=city)
