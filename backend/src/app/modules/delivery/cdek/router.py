from logging import getLogger

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from src.app.modules.auth.dependencies import get_current_user
from src.app.services.cache import build_cache_key, get_cache_service
from src.app.services.delivery_quotes import calculate_authoritative_cdek_quote
from src.database import get_db
from src.database.crud import get_basket_by_user_id
from src.database.models import User
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
async def cdek_delivery_calculate(
    latitude: float = Query(..., alias="latitude"),
    longitude: float = Query(..., alias="longitude"),
    mode: CdekDeliveryMode = Query(..., alias="mode"),
    country_code: CountryCode | None = Query(None, alias="country_code"),
    postal_code: str | None = Query(None, alias="postal_code"),
    address: str | None = Query(None, alias="address"),
    city: str | None = Query(None, alias="city"),
    delivery_point_code: str | None = Query(None, alias="delivery_point_code"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    cdek: AsyncCDEKClient = Depends(get_cdek_client),
):
    basket = await get_basket_by_user_id(db, current_user.id)
    if basket is None or not basket.items:
        raise HTTPException(status_code=409, detail="Корзина пуста. Добавьте товар перед расчётом доставки.")

    result = await calculate_authoritative_cdek_quote(
        db,
        user=current_user,
        address={
            "provider": "CDEK",
            "mode": mode,
            "country_code": country_code,
            "postal_code": postal_code,
            "full_address": address,
            "city": city,
            "latitude": latitude,
            "longitude": longitude,
            "provider_reference": delivery_point_code,
        },
        items=basket.items,
        cdek=cdek,
    )
    return CDEKCalculatedDelivery.model_validate(result)
