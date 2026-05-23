from typing import Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from src.app.services.cache import build_cache_key, get_cache_service
from src.database import get_db
from src.database.crud import get_product_categories
from src.database.schemas import ProductCategoryRead

product_categories_router = APIRouter(prefix="/product-categories", tags=["product-categories"])
PRODUCT_CATEGORIES_CACHE_TTL_SECONDS = 30 * 60

@product_categories_router.get("", response_model=list[ProductCategoryRead])
async def product_categories_get(q: str | None = Query(default=None, min_length=1, max_length=100), name: str | None = Query(default=None, min_length=1, max_length=200), limit: int = Query(default=100, ge=1, le=100), offset: int = Query(default=0, ge=0), sort: Literal["newest", "name_asc", "name_desc"] | None = Query(default="name_asc"), db: AsyncSession = Depends(get_db)) -> list[ProductCategoryRead]:
    normalized_q = q.strip().lower() if q is not None else None
    normalized_name = name.strip() if name is not None else None
    cache = get_cache_service()
    base_key = build_cache_key(route="product-categories:list", params={
        "q": normalized_q,
        "name": normalized_name,
        "limit": limit,
        "offset": offset,
        "sort": sort,
    })
    cache_key = await cache.versioned_key("categories", base_key)
    cached_items = await cache.get_json(cache_key, key_prefix="product-categories:list")
    if cached_items is not None: return [ProductCategoryRead.model_validate(item) for item in cached_items]

    items = [ProductCategoryRead.model_validate(category)  for category in await get_product_categories(db, q=normalized_q, name=normalized_name, offset=offset, limit=limit, sort=sort)]
    await cache.set_json(cache_key, [item.model_dump(mode="json") for item in items], ttl_seconds=PRODUCT_CATEGORIES_CACHE_TTL_SECONDS, key_prefix="product-categories:list")
    return items
