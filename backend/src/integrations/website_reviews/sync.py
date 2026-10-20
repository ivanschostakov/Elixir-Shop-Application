import logging
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from src.app.services.cache import get_cache_service
from src.app.services.review_attachments import remove_review_attachment_file

from .client import WebsiteReviewSyncClient
from .pull import _pull_website_reviews
from .push import _push_app_reviews
from .schemas import WebsiteReviewSyncStats


log = logging.getLogger("integrations.website_reviews")


async def sync_reviews_with_website(db: AsyncSession) -> WebsiteReviewSyncStats:
    client = WebsiteReviewSyncClient()
    stats = WebsiteReviewSyncStats()
    created_files: list[Path] = []
    try:
        await _pull_website_reviews(db, client, stats, created_files)
        await _push_app_reviews(db, client, stats)
        await db.commit()
    
    except Exception:
        await db.rollback()
        for file_path in created_files: remove_review_attachment_file(file_path)
        raise
    
    if stats.imported or stats.updated_from_website or stats.attachments_imported or stats.attachments_linked:
        cache = get_cache_service()
        await cache.bump_namespace("reviews")
        await cache.bump_namespace("product")
        await cache.bump_namespace("catalog")
    
    log.info("Website review sync completed: %s", stats.as_dict())
    return stats
