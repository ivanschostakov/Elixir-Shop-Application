from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from starlette import status

from config import ufa_now
from src.app.modules.admin.helpers import ensure_not_stale, serialize_admin_review, serialize_banner
from src.app.modules.admin.schemas import (
    AdminBannerPayload,
    AdminBannerRead,
    AdminBannerUpdatePayload,
    AdminPage,
    AdminReviewModerationPayload,
    AdminReviewRead,
)
from src.app.services.admin import AdminContext, add_admin_audit, require_permission
from src.app.services.cache import get_cache_service
from src.database import get_db
from src.database.models import Banner, Product, Review

admin_content_router = APIRouter(tags=["admin_content"])


async def _bump_review_cache() -> None:
    cache = get_cache_service()
    await cache.bump_namespace("reviews")
    await cache.bump_namespace("product")
    await cache.bump_namespace("catalog")


async def _bump_banner_cache() -> None:
    await get_cache_service().bump_namespace("banners")


@admin_content_router.get("/reviews", response_model=AdminPage[AdminReviewRead])
async def list_reviews(
    request: Request,
    review_status: str | None = Query(default=None, alias="status", pattern="^(pending|published|rejected)$"),
    product_id: int | None = Query(default=None, ge=1),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    _: AdminContext = Depends(require_permission("reviews.read")),
) -> AdminPage[AdminReviewRead]:
    filters = []
    if review_status == "pending":
        filters.extend((Review.moderated.is_(False), Review.rejected_at.is_(None)))
    elif review_status == "published":
        filters.extend((Review.moderated.is_(True), Review.rejected_at.is_(None)))
    elif review_status == "rejected":
        filters.append(Review.rejected_at.is_not(None))
    if product_id:
        filters.append(Review.product_id == product_id)
    total = int((await db.execute(select(func.count(Review.id)).where(*filters))).scalar_one())
    rows = (await db.execute(select(Review, Product.name).join(Product, Product.id == Review.product_id).options(
        selectinload(Review.user),
        selectinload(Review.attachments),
    ).where(*filters).order_by(Review.created_at.desc(), Review.id.desc()).offset(offset).limit(limit))).all()
    return AdminPage(items=[serialize_admin_review(request, review, product_name=product_name) for review, product_name in rows], total=total, limit=limit, offset=offset)


async def _get_review(db: AsyncSession, review_id: int) -> tuple[Review, str]:
    row = (await db.execute(select(Review, Product.name).join(Product, Product.id == Review.product_id).options(
        selectinload(Review.user),
        selectinload(Review.attachments),
    ).where(Review.id == review_id).execution_options(populate_existing=True))).one_or_none()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Review not found")
    return row


@admin_content_router.patch("/reviews/{review_id}/moderation", response_model=AdminReviewRead)
async def moderate_review(
    review_id: int,
    payload: AdminReviewModerationPayload,
    request: Request,
    db: AsyncSession = Depends(get_db),
    context: AdminContext = Depends(require_permission("reviews.moderate", write=True)),
) -> AdminReviewRead:
    review, product_name = await _get_review(db, review_id)
    ensure_not_stale(actual=review.updated_at, expected=payload.expected_updated_at)
    before = serialize_admin_review(request, review, product_name=product_name).model_dump(mode="json")
    now = ufa_now()
    review.answer = payload.answer.strip() if payload.answer else None
    review.moderated_by_user_id = context.user.id
    review.moderated_at = now
    if payload.action == "publish":
        review.moderated = True
        review.rejected_at = None
    else:
        review.moderated = False
        review.rejected_at = now
    await db.flush()
    result = serialize_admin_review(request, review, product_name=product_name)
    await add_admin_audit(db, request, context, action=f"review.{payload.action}", entity_type="review", entity_id=review.id, before=before, after=result.model_dump(mode="json"))
    await db.commit()
    await _bump_review_cache()
    return result


@admin_content_router.get("/banners", response_model=AdminPage[AdminBannerRead])
async def list_banners(
    archived: bool | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    _: AdminContext = Depends(require_permission("banners.manage")),
) -> AdminPage[AdminBannerRead]:
    filters = [Banner.archived.is_(archived)] if archived is not None else []
    total = int((await db.execute(select(func.count(Banner.id)).where(*filters))).scalar_one())
    rows = list((await db.execute(select(Banner).where(*filters).order_by(Banner.priority.desc(), Banner.id.desc()).offset(offset).limit(limit))).scalars().all())
    return AdminPage(items=[serialize_banner(row) for row in rows], total=total, limit=limit, offset=offset)


@admin_content_router.post("/banners", response_model=AdminBannerRead, status_code=status.HTTP_201_CREATED)
async def create_banner(
    payload: AdminBannerPayload,
    request: Request,
    db: AsyncSession = Depends(get_db),
    context: AdminContext = Depends(require_permission("banners.manage", write=True)),
) -> AdminBannerRead:
    banner = Banner(**payload.model_dump())
    db.add(banner)
    await db.flush()
    result = serialize_banner(banner)
    await add_admin_audit(db, request, context, action="banner.create", entity_type="banner", entity_id=banner.id, after=result.model_dump(mode="json"))
    await db.commit()
    await _bump_banner_cache()
    return result


@admin_content_router.put("/banners/{banner_id}", response_model=AdminBannerRead)
async def update_banner(
    banner_id: int,
    payload: AdminBannerUpdatePayload,
    request: Request,
    db: AsyncSession = Depends(get_db),
    context: AdminContext = Depends(require_permission("banners.manage", write=True)),
) -> AdminBannerRead:
    banner = await db.get(Banner, banner_id)
    if banner is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Banner not found")
    ensure_not_stale(actual=banner.updated_at, expected=payload.expected_updated_at)
    before = serialize_banner(banner).model_dump(mode="json")
    for field, value in payload.model_dump(exclude={"expected_updated_at"}).items():
        setattr(banner, field, value)
    await db.flush()
    result = serialize_banner(banner)
    await add_admin_audit(db, request, context, action="banner.update", entity_type="banner", entity_id=banner.id, before=before, after=result.model_dump(mode="json"))
    await db.commit()
    await _bump_banner_cache()
    return result
