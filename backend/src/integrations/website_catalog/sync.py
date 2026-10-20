import logging
from pathlib import Path

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.app.services.cache import get_cache_service
from src.database.models import Product
from src.integrations.website_catalog_certificates import remove_local_certificate

from .categories import _sync_categories
from .certificates import _apply_certificates
from .client import WebsiteCatalogSyncClient
from .parsers import _parse_categories, _parse_content_rows
from .products import _apply_content, _match_content_rows
from .schemas import WebsiteCatalogSyncStats


log = logging.getLogger("integrations.website_catalog")


async def sync_catalog_content_with_website(session: AsyncSession, *, client: WebsiteCatalogSyncClient | None = None) -> WebsiteCatalogSyncStats:
    sync_client = client or WebsiteCatalogSyncClient()
    stats = WebsiteCatalogSyncStats()
    payload = await sync_client.pull()
    contents = _parse_content_rows(payload, stats, public_base_url=sync_client.public_base_url)
    categories = _parse_categories(payload, stats)
    if not contents: return stats

    products = list((await session.execute(select(Product).options(selectinload(Product.certificates)))).scalars().all())
    certificates_changed = False
    downloaded_paths: set[Path] = set()
    stale_paths: set[Path] = set()
    try:
        async with httpx.AsyncClient(timeout=sync_client.timeout, transport=sync_client.transport, follow_redirects=False) as download_client:
            for product, content in _match_content_rows(products, contents, stats):
                if _apply_content(product, content, stats): stats.updated_products += 1
                else: stats.unchanged += 1
                if await _apply_certificates(session, product, content.certificates, stats, download_client=download_client, downloaded_paths=downloaded_paths, stale_paths=stale_paths): certificates_changed = True

        categories_changed = await _sync_categories(session, categories, products, stats)

        changed = bool(stats.updated_products or certificates_changed or categories_changed)
        if changed: await session.commit()
    except Exception:
        await session.rollback()
        raise

    for stale_path in stale_paths - downloaded_paths:
        if remove_local_certificate(stale_path): stats.certificate_files_deleted += 1

    if changed:
        cache = get_cache_service()
        await cache.bump_namespace("catalog")
        await cache.bump_namespace("product")
        if categories_changed: await cache.bump_namespace("categories")
    return stats
