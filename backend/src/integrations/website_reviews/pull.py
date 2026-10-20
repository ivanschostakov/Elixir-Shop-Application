from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.database.models import Product, Review, ReviewModerationEvent, Variant

from .attachments import _sync_remote_attachments
from .client import PAGE_SIZE, WebsiteReviewSyncClient
from .schemas import WebsiteReviewSyncStats
from .utils import _local_review_for_remote, _parse_datetime, _remote_values, _review_state


async def _pull_website_reviews(db: AsyncSession, client: WebsiteReviewSyncClient, stats: WebsiteReviewSyncStats, created_files: list[Path]) -> None:
    offset = 0
    while True:
        response = await client.request("pull", {"offset": offset, "limit": PAGE_SIZE})
        rows = response.get("reviews")
        if not isinstance(rows, list): raise RuntimeError("Website review sync returned an invalid review list")
        if not rows: break

        product_keys: dict[str, UUID] = {}
        for row in rows:
            raw_key = str(row.get("product_system_id") or "")
            try: product_keys[raw_key] = UUID(raw_key)
            except ValueError: continue
        
        products = list((await db.execute(select(Product).where(Product.system_id.in_(list(product_keys.values()))))).scalars().all()) if product_keys else []
        products_by_key = {str(product.system_id): product for product in products}
        missing_keys = {system_id for system_id in product_keys.values() if str(system_id) not in products_by_key}
        if missing_keys:
            variants = (await db.execute(select(Variant, Product).join(Product, Product.id == Variant.product_id).where(Variant.system_id.in_(list(missing_keys))))).all()
            for variant, product in variants: products_by_key.setdefault(str(variant.system_id), product)

        remote_ids = [int(row["remote_id"]) for row in rows if str(row.get("remote_id") or "").isdigit()]
        app_review_ids = [int(row["app_review_id"]) for row in rows if str(row.get("app_review_id") or "").isdigit()]
        review_filters = []
        if remote_ids: review_filters.append(Review.website_review_id.in_(remote_ids))
        if app_review_ids: review_filters.append(Review.id.in_(app_review_ids))
        
        existing_reviews = list((await db.execute(select(Review).options(selectinload(Review.attachments)).where(or_(*review_filters)))).scalars().all()) if review_filters else []
        existing_by_remote_id = {int(review.website_review_id): review for review in existing_reviews if review.website_review_id}
        existing_by_app_id = {int(review.id): review for review in existing_reviews if review.id}

        for row in rows:
            stats.pulled += 1
            remote_id = int(row.get("remote_id") or 0)
            product = products_by_key.get(str(row.get("product_system_id") or ""))
            if remote_id <= 0 or product is None:
                stats.skipped_missing_product += 1
                continue
            
            remote_updated_at = _parse_datetime(row.get("updated_at")) or _parse_datetime(row.get("created_at"))
            review = _local_review_for_remote(row, product_id=product.id, existing_by_remote_id=existing_by_remote_id, existing_by_app_id=existing_by_app_id)
            values = _remote_values(row)
            if review is None:
                review = Review(user_id=None, product_id=product.id, sync_origin="website", website_review_id=remote_id, website_updated_at=remote_updated_at, created_at=_parse_datetime(row.get("created_at")) or datetime.now(timezone.utc), updated_at=remote_updated_at or _parse_datetime(row.get("created_at")) or datetime.now(timezone.utc), attachments=[], **values)
                db.add(review)
                await db.flush()
                existing_by_remote_id[remote_id] = review
                stats.imported += 1
            
            else:
                previous_state = _review_state(review)
                previous_website_updated_at = review.website_updated_at
                remote_advanced = remote_updated_at is not None and (previous_website_updated_at is None or remote_updated_at > previous_website_updated_at)
                local_conflict = (
                    remote_advanced
                    and previous_website_updated_at is not None
                    and review.updated_at is not None
                    and review.updated_at > previous_website_updated_at
                    and remote_updated_at is not None
                    and review.updated_at > remote_updated_at
                )
                
                authority_keys = {"answer", "moderated", "moderated_at", "rejected_at"}
                values_to_apply = {key: value for key, value in values.items() if key in authority_keys} if local_conflict or not remote_advanced else values
                changed = any(getattr(review, key) != value for key, value in values_to_apply.items())
                if changed:
                    for key, value in values_to_apply.items(): setattr(review, key, value)
                    review.product_id = product.id
                    stats.updated_from_website += 1
                
                if local_conflict: stats.conflicts += 1
                if remote_advanced: review.website_updated_at = remote_updated_at
                if remote_updated_at is not None and remote_advanced and not local_conflict: review.updated_at = remote_updated_at
                
                current_state = _review_state(review)
                if current_state != previous_state:
                    action = {
                        "published": "review.publish",
                        "rejected": "review.reject",
                        "pending": "review.restore",
                    }[current_state]
                    db.add(ReviewModerationEvent(review_id=review.id, actor_user_id=None, action=action, before_json={"status": previous_state}, after_json={"status": current_state}, metadata_json={
                        "source": "bitrix",
                        "website_review_id": remote_id,
                    }))

            await _sync_remote_attachments(db, review, row, stats, created_files)

        await db.flush()
        offset += len(rows)
        if len(rows) < PAGE_SIZE: break
