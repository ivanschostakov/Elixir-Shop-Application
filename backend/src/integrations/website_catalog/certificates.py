from pathlib import Path

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.models import Product, ProductCertificate
from src.integrations.website_catalog_certificates import certificate_local_path_from_url, mirror_certificate

from .schemas import WebsiteCatalogCertificate, WebsiteCatalogSyncStats


async def _apply_certificates(session: AsyncSession, product: Product, certificates: tuple[WebsiteCatalogCertificate, ...] | None, stats: WebsiteCatalogSyncStats, *, download_client: httpx.AsyncClient, downloaded_paths: set[Path], stale_paths: set[Path]) -> bool:
    if certificates is None: return False

    changed = False
    existing_by_file_id = {certificate.website_file_id: certificate for certificate in product.certificates}
    desired_file_ids = {certificate.source_file_id for certificate in certificates}

    for sort_order, remote in enumerate(certificates):
        certificate = existing_by_file_id.get(remote.source_file_id)
        mirrored = await mirror_certificate(download_client, product_id=product.id, source_file_id=remote.source_file_id, source_url=remote.source_url, original_name=remote.original_name, content_type=remote.content_type, expected_size_bytes=remote.size_bytes)
        if mirrored.downloaded:
            downloaded_paths.add(mirrored.path)
            stats.certificates_downloaded += 1
            stats.certificate_bytes_downloaded += mirrored.size_bytes
        
        if certificate is None:
            session.add(ProductCertificate(product_id=product.id, website_file_id=remote.source_file_id, title=remote.title, original_name=remote.original_name, content_type=mirrored.content_type, size_bytes=mirrored.size_bytes, url=mirrored.url, sort_order=sort_order))
            stats.certificates_created += 1
            changed = True
            continue

        previous_path = certificate_local_path_from_url(certificate.url)
        certificate_changed = False
        for field, value in (
            ("title", remote.title),
            ("original_name", remote.original_name),
            ("content_type", mirrored.content_type),
            ("size_bytes", mirrored.size_bytes),
            ("url", mirrored.url),
            ("sort_order", sort_order),
        ):
            if getattr(certificate, field) == value: continue
            setattr(certificate, field, value)
            certificate_changed = True
        
        if certificate_changed:
            stats.certificates_updated += 1
            changed = True
        
        if previous_path is not None and previous_path != mirrored.path: stale_paths.add(previous_path)

    for source_file_id, certificate in existing_by_file_id.items():
        if source_file_id in desired_file_ids: continue
        local_path = certificate_local_path_from_url(certificate.url)
        if local_path is not None: stale_paths.add(local_path)
        await session.delete(certificate)
        stats.certificates_deleted += 1
        changed = True

    return changed
