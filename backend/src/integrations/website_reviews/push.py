import logging
from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.database.models import Product, Review, User

from .client import PAGE_SIZE, WebsiteReviewSyncClient, website_review_sync_configured
from .schemas import WebsiteReviewSyncStats
from .utils import _mark_review_synced, _push_payload


log = logging.getLogger("integrations.website_reviews")


async def _push_app_reviews(db: AsyncSession, client: WebsiteReviewSyncClient, stats: WebsiteReviewSyncStats) -> None:
    last_review_id = 0
    while True:
        rows = (await db.execute(select(Review, Product.system_id, User.email, User.name, User.surname).options(selectinload(Review.attachments)).join(Product, Product.id == Review.product_id).outerjoin(User, User.id == Review.user_id).where(Product.system_id.is_not(None)).where(Review.id > last_review_id).where(
            or_(Review.website_review_id.is_(None), Review.website_updated_at.is_(None), Review.updated_at > Review.website_updated_at)
        ).order_by(Review.id).limit(PAGE_SIZE))).all()
        if not rows: break

        await _push_rows(db, client, stats, rows)
        last_review_id = rows[-1][0].id
        if len(rows) < PAGE_SIZE: break


async def _push_rows(db: AsyncSession, client: WebsiteReviewSyncClient, stats: WebsiteReviewSyncStats, rows: list[Any]) -> None:
    payload = [_push_payload(review, system_id=system_id, email=email, name=name, surname=surname) for review, system_id, email, name, surname in rows]
    response = await client.request("push", {"reviews": payload})
    
    results = response.get("results")
    if not isinstance(results, list): raise RuntimeError("Website review sync returned invalid push results")
    reviews_by_id = {review.id: review for review, *_ in rows}
    for result in results:
        app_review_id = int(result.get("app_review_id") or 0)
        review = reviews_by_id.get(app_review_id)
        if review is None: continue
        
        outcome = str(result.get("outcome") or "")
        if outcome == "skipped_missing_product":
            stats.skipped_missing_product += 1
            continue
        
        _mark_review_synced(review, result)
        if outcome == "created": stats.created_on_website += 1
        elif outcome == "updated": stats.updated_on_website += 1
        elif outcome == "conflict": stats.conflicts += 1
        stats.pushed += 1
    await db.flush()


async def push_review_to_website(db: AsyncSession, *, review_id: int) -> WebsiteReviewSyncStats:
    if not website_review_sync_configured(): raise RuntimeError("Website review sync is not configured")
    
    row = (await db.execute(select(Review, Product.system_id, User.email, User.name, User.surname).options(selectinload(Review.attachments)).join(Product, Product.id == Review.product_id).outerjoin(User, User.id == Review.user_id).where(Review.id == review_id, Product.system_id.is_not(None)).execution_options(populate_existing=True))).one_or_none()
    if row is None: raise RuntimeError("Review product mapping is missing")
    
    stats = WebsiteReviewSyncStats()
    await _push_rows(db, WebsiteReviewSyncClient(), stats, [row])
    await db.commit()
    return stats


async def push_review_to_website_safely(db: AsyncSession, *, review_id: int) -> bool:
    if not website_review_sync_configured():
        log.warning("Review %s was saved locally; website review sync is not configured", review_id)
        return False
    
    try:
        await push_review_to_website(db, review_id=review_id)
        return True
    
    except Exception:
        await db.rollback()
        log.exception("Review %s was saved locally but immediate Bitrix delivery failed; " "the sync worker will retry", review_id)
        return False
