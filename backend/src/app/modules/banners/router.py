from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from src.app.modules.auth.dependencies import get_optional_current_user
from src.app.services.cache import build_cache_key, get_cache_service
from src.app.services.rate_limit import client_ip_from_request
from src.app.services.customer_intelligence import record_customer_event_safe
from src.database import get_db
from src.database.crud import get_banner_by_id, get_banners
from src.database.models import Banner, BannerClick, User
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


@banners_router.post("/{banner_id}/click", status_code=204)
async def banner_click(
    banner_id: int,
    request: Request,
    target_url: str | None = Query(default=None, max_length=2048),
    db: AsyncSession = Depends(get_db),
    current_user: User | None = Depends(get_optional_current_user),
) -> None:
    banner = await get_banner_by_id(db, banner_id)
    if banner is None:
        raise HTTPException(status_code=404, detail="Banner not found")
    db.add(BannerClick(
        banner_id=banner.id,
        user_id=current_user.id if current_user else None,
        ip_address=client_ip_from_request(request),
        user_agent=(request.headers.get("user-agent") or "")[:512] or None,
        target_url=target_url,
        metadata_json={},
    ))
    await db.execute(update(Banner).where(Banner.id == banner.id).values(click_count=Banner.click_count + 1))
    if current_user is not None:
        await record_customer_event_safe(
            db,
            user_id=current_user.id,
            event_name="banner_clicked",
            entity_type="banner",
            entity_id=banner.id,
            properties={"target_url": target_url},
        )
    await db.commit()
