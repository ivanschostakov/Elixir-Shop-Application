from typing import Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from src.app.services.cache import build_cache_key, get_cache_service
from src.database import get_db
from src.database.crud import get_banners
from src.database.schemas import BannerRead

banners_router = APIRouter(prefix="/banners", tags=["banners"])
BANNERS_CACHE_TTL_SECONDS = 10 * 60


@banners_router.get("", response_model=list[BannerRead])
async def banners_get(limit: int = Query(default=10, ge=1, le=50), offset: int = Query(default=0, ge=0), sort: Literal["newest", "priority_desc", "priority_asc"] | None = Query(default="priority_desc"), db: AsyncSession = Depends(get_db)) -> list[BannerRead]:
    cache = get_cache_service()
    base_key = build_cache_key(route="banners:list", params={
        "limit": limit,
        "offset": offset,
        "sort": sort,
    })
    cache_key = await cache.versioned_key("banners", base_key)
    cached_items = await cache.get_json(cache_key, key_prefix="banners:list")
    if cached_items is not None: return [BannerRead.model_validate(item) for item in cached_items]
    items = [BannerRead.model_validate(banner) for banner in await get_banners(db, offset=offset, limit=limit, sort=sort)]
    await cache.set_json(cache_key, [item.model_dump(mode="json") for item in items], ttl_seconds=BANNERS_CACHE_TTL_SECONDS, key_prefix="banners:list")
    return items
