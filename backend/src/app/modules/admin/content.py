from pathlib import Path
from uuid import uuid4
from urllib.parse import urlsplit

import aiofiles
from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile
from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, selectinload
from starlette import status

from config import MEDIA_DIR, ufa_now
from src.app.modules.admin.helpers import (
    ensure_not_stale,
    serialize_admin_review,
    serialize_banner,
    serialize_business_content,
    serialize_business_content_version,
    serialize_review_moderation_event,
)
from src.app.modules.admin.schemas import (
    AdminBannerPayload,
    AdminBannerRead,
    AdminBannerUploadRead,
    AdminBusinessContentRead,
    AdminBusinessContentUpdatePayload,
    AdminBusinessContentVersionRead,
    AdminBannerUpdatePayload,
    AdminPage,
    AdminReviewModerationPayload,
    AdminReviewBulkModerationPayload,
    AdminReviewModerationEventRead,
    AdminReviewRead,
)
from src.app.services.admin import AdminContext, add_admin_audit, require_permission
from src.app.services.cache import get_cache_service
from src.app.services.push_notifications import send_push_to_user
from src.app.services.review_attachments import validate_review_attachment
from src.database import get_db
from src.database.models import (
    Admin,
    Banner,
    BusinessContentPage,
    BusinessContentVersion,
    NotificationDispatch,
    Product,
    Review,
    ReviewAttachment,
    ReviewModerationEvent,
)

admin_content_router = APIRouter(tags=["admin_content"])
BANNERS_MEDIA_DIR = MEDIA_DIR / "banners"
BANNERS_MEDIA_DIR.mkdir(parents=True, exist_ok=True)


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
    rating: int | None = Query(default=None, ge=0, le=5),
    flagged: bool | None = Query(default=None),
    q: str | None = Query(default=None, max_length=120),
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
    if rating is not None:
        filters.append(Review.value == rating)
    if flagged is True:
        filters.append(or_(Review.spam_score >= 50, Review.profanity_flag.is_(True), Review.duplicate_flag.is_(True), Review.suspicious_ip_flag.is_(True)))
    elif flagged is False:
        filters.append(and_(Review.spam_score < 50, Review.profanity_flag.is_(False), Review.duplicate_flag.is_(False), Review.suspicious_ip_flag.is_(False)))
    if q:
        pattern = f"%{q.strip()}%"
        filters.append(or_(Review.text.ilike(pattern), Review.guest_name.ilike(pattern), Review.guest_email.ilike(pattern), Product.name.ilike(pattern)))
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


def _review_moderation_snapshot(request: Request, review: Review, product_name: str) -> dict:
    return serialize_admin_review(request, review, product_name=product_name).model_dump(mode="json")


async def _record_review_event(
    db: AsyncSession,
    *,
    review: Review,
    context: AdminContext,
    action: str,
    before: dict | None,
    after: dict | None,
    comment: str | None,
    metadata: dict | None = None,
) -> None:
    db.add(ReviewModerationEvent(
        review_id=review.id,
        actor_user_id=context.user.id,
        action=action,
        comment=comment,
        before_json=before,
        after_json=after,
        metadata_json=metadata or {},
    ))
    await db.flush()


async def _notify_review_published(db: AsyncSession, review: Review) -> None:
    if review.user_id is None or review.customer_notified_at is not None:
        return
    dedupe_key = f"review:{review.id}:published"
    existing = (await db.execute(select(NotificationDispatch.id).where(
        NotificationDispatch.user_id == review.user_id,
        NotificationDispatch.type == "review_published",
        NotificationDispatch.dedupe_key == dedupe_key,
    ).limit(1))).scalar_one_or_none()
    if existing is not None:
        review.customer_notified_at = ufa_now()
        return
    sent = False
    try:
        sent = await send_push_to_user(
            db,
            user_id=review.user_id,
            title="Ваш отзыв опубликован",
            body="Спасибо, что поделились опытом — отзыв уже на витрине.",
            data={"type": "review_published", "review_id": review.id, "product_id": review.product_id},
        )
    except Exception:
        sent = False
    db.add(NotificationDispatch(
        user_id=review.user_id,
        type="review_published",
        dedupe_key=dedupe_key,
        payload_json={"review_id": review.id, "product_id": review.product_id, "push_sent": sent},
        sent_at=ufa_now(),
    ))
    review.customer_notified_at = ufa_now()


def _apply_attachment_statuses(review: Review, payload: AdminReviewModerationPayload, *, actor_user_id: int) -> dict[int, str]:
    applied: dict[int, str] = {}
    if not payload.attachment_statuses:
        return applied
    now = ufa_now()
    attachments_by_id = {attachment.id: attachment for attachment in review.attachments}
    for attachment_id, moderation_status in payload.attachment_statuses.items():
        attachment = attachments_by_id.get(int(attachment_id))
        if attachment is None:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"Attachment {attachment_id} does not belong to this review")
        attachment.moderation_status = moderation_status
        attachment.moderated_at = now
        attachment.moderated_by_user_id = actor_user_id
        applied[int(attachment_id)] = moderation_status
    return applied


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
    before = _review_moderation_snapshot(request, review, product_name)
    now = ufa_now()
    review.answer = payload.answer.strip() if payload.answer else None
    review.internal_moderation_comment = payload.internal_comment.strip() if payload.internal_comment else review.internal_moderation_comment
    review.moderated_by_user_id = context.user.id
    review.moderated_at = now
    attachment_statuses = _apply_attachment_statuses(review, payload, actor_user_id=context.user.id)
    if payload.action == "publish":
        review.moderated = True
        review.rejected_at = None
        review.appeal_status = "none"
        await _notify_review_published(db, review)
    elif payload.action == "restore":
        review.moderated = False
        review.rejected_at = None
        review.restored_at = now
        review.appeal_status = "restored"
    else:
        review.moderated = False
        review.rejected_at = now
        review.appeal_status = "none"
    await db.flush()
    result = serialize_admin_review(request, review, product_name=product_name)
    after = result.model_dump(mode="json")
    await _record_review_event(
        db,
        review=review,
        context=context,
        action=payload.action,
        before=before,
        after=after,
        comment=payload.internal_comment,
        metadata={"attachment_statuses": attachment_statuses},
    )
    await add_admin_audit(db, request, context, action=f"review.{payload.action}", entity_type="review", entity_id=review.id, before=before, after=after)
    await db.commit()
    await _bump_review_cache()
    return result


@admin_content_router.get("/reviews/{review_id}/moderation-history", response_model=list[AdminReviewModerationEventRead])
async def review_moderation_history(
    review_id: int,
    db: AsyncSession = Depends(get_db),
    _: AdminContext = Depends(require_permission("reviews.read")),
) -> list[AdminReviewModerationEventRead]:
    review = await db.get(Review, review_id)
    if review is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Review not found")
    rows = list((await db.execute(
        select(ReviewModerationEvent)
        .options(joinedload(ReviewModerationEvent.actor).joinedload(Admin.user))
        .where(ReviewModerationEvent.review_id == review_id)
        .order_by(ReviewModerationEvent.created_at.asc(), ReviewModerationEvent.id.asc())
    )).scalars().all())
    return [AdminReviewModerationEventRead.model_validate(serialize_review_moderation_event(row)) for row in rows]


@admin_content_router.post("/reviews/bulk-moderation", response_model=list[AdminReviewRead])
async def bulk_moderate_reviews(
    payload: AdminReviewBulkModerationPayload,
    request: Request,
    db: AsyncSession = Depends(get_db),
    context: AdminContext = Depends(require_permission("reviews.moderate", write=True)),
) -> list[AdminReviewRead]:
    item_by_id = {item.id: item for item in payload.items}
    if len(item_by_id) != len(payload.items):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Review IDs must be unique")

    now = ufa_now()
    results: list[AdminReviewRead] = []
    for review_id, item in item_by_id.items():
        review, product_name = await _get_review(db, review_id)
        ensure_not_stale(actual=review.updated_at, expected=item.expected_updated_at)
        before = _review_moderation_snapshot(request, review, product_name)
        review.answer = None
        review.internal_moderation_comment = payload.internal_comment
        review.moderated_by_user_id = context.user.id
        review.moderated_at = now
        if payload.action == "publish":
            review.moderated = True
            review.rejected_at = None
        else:
            review.moderated = False
            review.rejected_at = now
        await db.flush()
        serialized = serialize_admin_review(request, review, product_name=product_name)
        results.append(serialized)
        await _record_review_event(
            db,
            review=review,
            context=context,
            action=f"bulk.{payload.action}",
            before=before,
            after=serialized.model_dump(mode="json"),
            comment=payload.internal_comment,
            metadata={},
        )

    await add_admin_audit(
        db,
        request,
        context,
        action=f"review.bulk.{payload.action}",
        entity_type="review",
        entity_id=None,
        after={"review_ids": list(item_by_id), "count": len(item_by_id)},
    )
    await db.commit()
    await _bump_review_cache()
    return results


@admin_content_router.post("/reviews/bulk-reject-spam", response_model=list[AdminReviewRead])
async def bulk_reject_spam_reviews(
    request: Request,
    db: AsyncSession = Depends(get_db),
    context: AdminContext = Depends(require_permission("reviews.moderate", write=True)),
) -> list[AdminReviewRead]:
    rows = (await db.execute(
        select(Review, Product.name)
        .join(Product, Product.id == Review.product_id)
        .options(selectinload(Review.user), selectinload(Review.attachments))
        .where(
            Review.moderated.is_(False),
            Review.rejected_at.is_(None),
            or_(Review.spam_score >= 70, Review.profanity_flag.is_(True), Review.suspicious_ip_flag.is_(True)),
        )
        .order_by(Review.spam_score.desc(), Review.created_at.asc())
        .limit(200)
    )).all()
    now = ufa_now()
    results: list[AdminReviewRead] = []
    for review, product_name in rows:
        before = _review_moderation_snapshot(request, review, product_name)
        review.moderated = False
        review.rejected_at = now
        review.moderated_at = now
        review.moderated_by_user_id = context.user.id
        review.internal_moderation_comment = "Bulk spam rejection"
        await db.flush()
        serialized = serialize_admin_review(request, review, product_name=product_name)
        results.append(serialized)
        await _record_review_event(db, review=review, context=context, action="bulk.reject_spam", before=before, after=serialized.model_dump(mode="json"), comment="Bulk spam rejection", metadata={})
    await add_admin_audit(db, request, context, action="review.bulk.reject_spam", entity_type="review", entity_id=None, after={"count": len(results), "review_ids": [row.id for row in results]})
    await db.commit()
    await _bump_review_cache()
    return results


@admin_content_router.get("/banners", response_model=AdminPage[AdminBannerRead])
async def list_banners(
    archived: bool | None = None,
    banner_status: str | None = Query(default=None, alias="status", pattern="^(draft|scheduled|published|archived)$"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    _: AdminContext = Depends(require_permission("banners.manage")),
) -> AdminPage[AdminBannerRead]:
    filters = [Banner.archived.is_(archived)] if archived is not None else []
    if banner_status:
        filters.append(Banner.status == banner_status)
    total = int((await db.execute(select(func.count(Banner.id)).where(*filters))).scalar_one())
    rows = list((await db.execute(select(Banner).where(*filters).order_by(Banner.priority.desc(), Banner.id.desc()).offset(offset).limit(limit))).scalars().all())
    return AdminPage(items=[serialize_banner(row) for row in rows], total=total, limit=limit, offset=offset)


def _validate_banner_payload(payload: AdminBannerPayload) -> None:
    if not (payload.image_path or payload.desktop_image_path or payload.mobile_image_path):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Banner image is required")
    if payload.inner_link and not payload.inner_link.startswith("/"):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Internal banner link must start with /")
    if payload.outer_link:
        parsed = urlsplit(payload.outer_link)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="External banner link must be a valid URL")
    if payload.starts_at and payload.ends_at and payload.ends_at <= payload.starts_at:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Banner end date must be after start date")


def _normalize_banner_payload(payload: AdminBannerPayload) -> dict:
    _validate_banner_payload(payload)
    data = payload.model_dump()
    if payload.status == "archived":
        data["archived"] = True
    elif payload.archived:
        data["status"] = "archived"
    if not data.get("image_path"):
        data["image_path"] = data.get("desktop_image_path") or data.get("mobile_image_path")
    return data


def _banner_public_url(request: Request, image_path: str) -> str:
    if image_path.startswith("http://") or image_path.startswith("https://"):
        return image_path
    return f"{str(request.base_url).rstrip('/')}{image_path if image_path.startswith('/') else '/' + image_path}"


@admin_content_router.post("/banners/upload", response_model=AdminBannerUploadRead)
async def upload_banner_image(
    request: Request,
    file: UploadFile = File(...),
    _: AdminContext = Depends(require_permission("banners.manage", write=True)),
) -> AdminBannerUploadRead:
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
async def create_banner(
    payload: AdminBannerPayload,
    request: Request,
    db: AsyncSession = Depends(get_db),
    context: AdminContext = Depends(require_permission("banners.manage", write=True)),
) -> AdminBannerRead:
    banner = Banner(**_normalize_banner_payload(payload))
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
    data = _normalize_banner_payload(payload)
    data.pop("expected_updated_at", None)
    for field, value in data.items():
        setattr(banner, field, value)
    await db.flush()
    result = serialize_banner(banner)
    await add_admin_audit(db, request, context, action="banner.update", entity_type="banner", entity_id=banner.id, before=before, after=result.model_dump(mode="json"))
    await db.commit()
    await _bump_banner_cache()
    return result


@admin_content_router.get("/business-content", response_model=AdminPage[AdminBusinessContentRead])
async def list_business_content(
    content_status: str | None = Query(default=None, alias="status", pattern="^(draft|published|archived)$"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    _: AdminContext = Depends(require_permission("banners.manage")),
) -> AdminPage[AdminBusinessContentRead]:
    filters = [BusinessContentPage.status == content_status] if content_status else []
    total = int((await db.execute(select(func.count(BusinessContentPage.id)).where(*filters))).scalar_one())
    rows = list((await db.execute(
        select(BusinessContentPage)
        .options(joinedload(BusinessContentPage.updated_by).joinedload(Admin.user))
        .where(*filters)
        .order_by(BusinessContentPage.code.asc())
        .offset(offset)
        .limit(limit)
    )).scalars().all())
    return AdminPage(items=[serialize_business_content(row) for row in rows], total=total, limit=limit, offset=offset)


@admin_content_router.put("/business-content/{code}", response_model=AdminBusinessContentRead)
async def update_business_content(
    code: str,
    payload: AdminBusinessContentUpdatePayload,
    request: Request,
    db: AsyncSession = Depends(get_db),
    context: AdminContext = Depends(require_permission("banners.manage", write=True)),
) -> AdminBusinessContentRead:
    page = (await db.execute(
        select(BusinessContentPage)
        .options(joinedload(BusinessContentPage.updated_by).joinedload(Admin.user))
        .where(BusinessContentPage.code == code)
        .execution_options(populate_existing=True)
    )).scalar_one_or_none()
    if page is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Business content page not found")
    ensure_not_stale(actual=page.updated_at, expected=payload.expected_updated_at)
    before = serialize_business_content(page).model_dump(mode="json")
    page.version += 1
    page.title_ru = payload.title_ru
    page.title_en = payload.title_en
    page.body_ru = payload.body_ru
    page.body_en = payload.body_en
    page.link_url = payload.link_url
    page.status = payload.status
    page.metadata_json = payload.metadata_json
    page.updated_by_user_id = context.user.id
    db.add(BusinessContentVersion(
        page_id=page.id,
        version=page.version,
        actor_user_id=context.user.id,
        snapshot_json={
            "code": page.code,
            "title_ru": page.title_ru,
            "title_en": page.title_en,
            "body_ru": page.body_ru,
            "body_en": page.body_en,
            "link_url": page.link_url,
            "status": page.status,
            "metadata_json": page.metadata_json,
        },
    ))
    await db.flush()
    page = (await db.execute(
        select(BusinessContentPage)
        .options(joinedload(BusinessContentPage.updated_by).joinedload(Admin.user))
        .where(BusinessContentPage.id == page.id)
        .execution_options(populate_existing=True)
    )).scalar_one()
    result = serialize_business_content(page)
    await add_admin_audit(db, request, context, action="business_content.update", entity_type="business_content", entity_id=page.code, before=before, after=result.model_dump(mode="json"))
    await db.commit()
    return result


@admin_content_router.get("/business-content/{code}/versions", response_model=list[AdminBusinessContentVersionRead])
async def business_content_versions(
    code: str,
    db: AsyncSession = Depends(get_db),
    _: AdminContext = Depends(require_permission("banners.manage")),
) -> list[AdminBusinessContentVersionRead]:
    page_id = (await db.execute(select(BusinessContentPage.id).where(BusinessContentPage.code == code))).scalar_one_or_none()
    if page_id is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Business content page not found")
    rows = list((await db.execute(
        select(BusinessContentVersion)
        .options(joinedload(BusinessContentVersion.actor).joinedload(Admin.user))
        .where(BusinessContentVersion.page_id == page_id)
        .order_by(BusinessContentVersion.version.desc(), BusinessContentVersion.id.desc())
    )).scalars().all())
    return [serialize_business_content_version(row) for row in rows]
