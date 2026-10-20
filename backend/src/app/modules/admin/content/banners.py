from datetime import timedelta
from decimal import Decimal
from uuid import uuid4
from urllib.parse import urlsplit
import aiofiles
from fastapi import Depends, File, HTTPException, Query, Request, UploadFile
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status
from config import ufa_now
from src.app.modules.admin.helpers import ensure_not_stale, serialize_banner
from src.app.modules.admin.schemas import AdminBannerPayload, AdminBannerRead, AdminBannerDailyStatRead, AdminBannerStatsRead, AdminBannerUploadRead, AdminBannerUpdatePayload, AdminPage
from src.app.services.admin import AdminContext, add_admin_audit, require_permission
from src.app.services.review_attachments import validate_review_attachment
from src.database import get_db
from src.database.models import Banner, BannerClick, BannerImpression
from .common import ANALYTICS_TIMEZONE, BANNERS_MEDIA_DIR, SUPPORTED_BANNER_ROUTES, admin_content_router
from .helpers import _bump_banner_cache


@admin_content_router.get("/banners", response_model=AdminPage[AdminBannerRead])
async def list_banners(archived: bool | None = None, banner_status: str | None = Query(default=None, alias="status", pattern="^(draft|scheduled|published|archived)$"), limit: int = Query(default=50, ge=1, le=200), offset: int = Query(default=0, ge=0), db: AsyncSession = Depends(get_db), _: AdminContext = Depends(require_permission("banners.manage")),) -> AdminPage[AdminBannerRead]:
    filters = [Banner.archived.is_(archived)] if archived is not None else []
    if banner_status: filters.append(Banner.status == banner_status)
    total = int((await db.execute(select(func.count(Banner.id)).where(*filters))).scalar_one())
    rows = list((await db.execute(select(Banner).where(*filters).order_by(Banner.priority.desc(), Banner.id.desc()).offset(offset).limit(limit))).scalars().all())
    return AdminPage(items=[serialize_banner(row) for row in rows], total=total, limit=limit, offset=offset)


@admin_content_router.get(
    "/banners/{banner_id}/stats",
    response_model=AdminBannerStatsRead,
)
async def get_banner_stats(banner_id: int, days: int = Query(default=30, ge=1, le=365), db: AsyncSession = Depends(get_db), _: AdminContext = Depends(require_permission("banners.manage")),) -> AdminBannerStatsRead:
    banner = await db.get(Banner, banner_id)
    if banner is None: raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Banner not found")
    now = ufa_now()
    start = (now - timedelta(days=days - 1)).replace(hour=0, minute=0, second=0, microsecond=0,)
    local_click_time = func.timezone(ANALYTICS_TIMEZONE, BannerClick.created_at)
    local_impression_time = func.timezone(ANALYTICS_TIMEZONE, BannerImpression.created_at,)
    click_rows = (await db.execute(select(func.date(local_click_time).label("day"), func.count(BannerClick.id).label("count"),).where(BannerClick.banner_id == banner_id, BannerClick.created_at >= start).group_by(func.date(local_click_time)))).all()
    impression_rows = (await db.execute(select(func.date(local_impression_time).label("day"), func.count(BannerImpression.id).label("count"),).where(BannerImpression.banner_id == banner_id, BannerImpression.created_at >= start,).group_by(func.date(local_impression_time)))).all()
    clicks_by_day = {row.day: int(row.count) for row in click_rows}
    impressions_by_day = {row.day: int(row.count) for row in impression_rows}
    daily: list[AdminBannerDailyStatRead] = []
    for offset in range(days):
        day = start.date() + timedelta(days=offset)
        clicks = clicks_by_day.get(day, 0)
        impressions = impressions_by_day.get(day, 0)
        daily.append(AdminBannerDailyStatRead(day=day, impressions=impressions, clicks=clicks, ctr_percent=(Decimal(clicks) / Decimal(impressions) * 100).quantize(Decimal("0.01")) if impressions else Decimal("0.00"),))
    clicks = int(banner.click_count or 0)
    impressions = int(banner.impression_count or 0)
    return AdminBannerStatsRead(banner_id=banner.id, impressions=impressions, clicks=clicks, ctr_percent=(Decimal(clicks) / Decimal(impressions) * 100).quantize(Decimal("0.01")) if impressions else Decimal("0.00"), daily=daily,)


def _validate_banner_payload(payload: AdminBannerPayload) -> None:
    if not (payload.image_path or payload.desktop_image_path or payload.mobile_image_path): raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Banner image is required")
    if payload.inner_link and payload.outer_link: raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Choose either an internal or external banner link, not both",)
    if payload.inner_link and not payload.inner_link.startswith("/"): raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Internal banner link must start with /")
    if payload.inner_link:
        path = urlsplit(payload.inner_link).path.rstrip("/") or "/"
        is_product = path.startswith("/products/") and path.removeprefix("/products/").isdigit()
        if path not in SUPPORTED_BANNER_ROUTES and not is_product: raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Internal banner link does not match a supported app route",)
    if payload.outer_link:
        parsed = urlsplit(payload.outer_link)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc: raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="External banner link must be a valid URL")
    if payload.starts_at and payload.ends_at and payload.ends_at <= payload.starts_at: raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Banner end date must be after start date")


def _normalize_banner_payload(payload: AdminBannerPayload) -> dict:
    _validate_banner_payload(payload)
    data = payload.model_dump()
    if payload.status == "archived": data["archived"] = True
    elif payload.archived: data["status"] = "archived"
    if not data.get("image_path"): data["image_path"] = data.get("desktop_image_path") or data.get("mobile_image_path")
    return data


def _banner_public_url(request: Request, image_path: str) -> str:
    if image_path.startswith("http://") or image_path.startswith("https://"): return image_path
    return f"{str(request.base_url).rstrip('/')}{image_path if image_path.startswith('/') else '/' + image_path}"


@admin_content_router.post("/banners/upload", response_model=AdminBannerUploadRead)
async def upload_banner_image(request: Request, file: UploadFile = File(...), _: AdminContext = Depends(require_permission("banners.manage", write=True)),) -> AdminBannerUploadRead:
    content = await file.read()
    mime_type = validate_review_attachment(content, mime_type=file.content_type)
    extension = {"image/jpeg": ".jpg", "image/jpg": ".jpg", "image/png": ".png", "image/webp": ".webp"}.get(mime_type, ".jpg")
    filename = f"{uuid4().hex}{extension}"
    path = BANNERS_MEDIA_DIR / filename
    async with aiofiles.open(path, "wb") as target:
        await target.write(content)
    public_path = f"/media/banners/{filename}"
    return AdminBannerUploadRead(image_path=public_path, url=_banner_public_url(request, public_path))


@admin_content_router.post("/banners", response_model=AdminBannerRead, status_code=status.HTTP_201_CREATED)
async def create_banner(payload: AdminBannerPayload, request: Request, db: AsyncSession = Depends(get_db), context: AdminContext = Depends(require_permission("banners.manage", write=True)),) -> AdminBannerRead:
    banner = Banner(**_normalize_banner_payload(payload))
    db.add(banner)
    await db.flush()
    result = serialize_banner(banner)
    await add_admin_audit(db, request, context, action="banner.create", entity_type="banner", entity_id=banner.id, after=result.model_dump(mode="json"))
    await db.commit()
    await _bump_banner_cache()
    return result


@admin_content_router.put("/banners/{banner_id}", response_model=AdminBannerRead)
async def update_banner(banner_id: int, payload: AdminBannerUpdatePayload, request: Request, db: AsyncSession = Depends(get_db), context: AdminContext = Depends(require_permission("banners.manage", write=True)),) -> AdminBannerRead:
    banner = await db.get(Banner, banner_id)
    if banner is None: raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Banner not found")
    ensure_not_stale(actual=banner.updated_at, expected=payload.expected_updated_at)
    before = serialize_banner(banner).model_dump(mode="json")
    data = _normalize_banner_payload(payload)
    data.pop("expected_updated_at", None)
    for field, value in data.items(): setattr(banner, field, value)
    await db.flush()
    result = serialize_banner(banner)
    await add_admin_audit(db, request, context, action="banner.update", entity_type="banner", entity_id=banner.id, before=before, after=result.model_dump(mode="json"))
    await db.commit()
    await _bump_banner_cache()
    return result
