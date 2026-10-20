import logging
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from config import WEBSITE_REVIEW_SYNC_ENDPOINT, WEBSITE_REVIEW_SYNC_TIMEOUT_SECONDS
from src.app.services.review_attachments import (MAX_REVIEW_IMAGES_COUNT, MAX_REVIEW_IMAGE_SIZE_BYTES, MAX_REVIEW_TOTAL_SIZE_BYTES, build_review_attachment_filename, save_review_attachment_file, validate_review_attachment)
from src.database.models import Review, ReviewAttachment

from .schemas import WebsiteReviewSyncStats
from .utils import _attachment_status


log = logging.getLogger("integrations.website_reviews")


def _valid_website_attachment_url(url: str) -> bool:
    candidate = urlsplit(url)
    endpoint = urlsplit(WEBSITE_REVIEW_SYNC_ENDPOINT)
    return (
        candidate.scheme == "https"
        and candidate.hostname is not None
        and candidate.hostname == endpoint.hostname
        and candidate.port in (None, 443)
        and not candidate.username
        and not candidate.password
        and candidate.path.startswith("/upload/sotbit.reviews/")
    )


async def _download_website_attachment(row: dict[str, Any]) -> tuple[str, str, bytes] | None:
    url = str(row.get("url") or "").strip()
    if not _valid_website_attachment_url(url): return None
    declared_size = max(0, int(row.get("size") or 0))
    if declared_size > MAX_REVIEW_IMAGE_SIZE_BYTES: return None
    async with httpx.AsyncClient(timeout=WEBSITE_REVIEW_SYNC_TIMEOUT_SECONDS, follow_redirects=False) as client: response = await client.get(url, headers={"Accept": "image/jpeg,image/png,image/webp"})
    if response.status_code == 404: return None
    response.raise_for_status()
    try: mime_type = validate_review_attachment(response.content, mime_type=response.headers.get("Content-Type") or str(row.get("mime_type") or ""))
    except Exception:
        log.warning("Bitrix review attachment %s failed image validation", url)
        return None
    filename = build_review_attachment_filename(mime_type)
    return filename, mime_type, response.content


async def _sync_remote_attachments(db: AsyncSession, review: Review, row: dict[str, Any], stats: WebsiteReviewSyncStats, created_files: list[Path]) -> None:
    remote_attachments = row.get("attachments")
    if not isinstance(remote_attachments, list): return
    attachments_by_id = {attachment.id: attachment for attachment in review.attachments}
    attachments_by_website_file_id = {
        attachment.website_file_id: attachment
        for attachment in review.attachments
        if attachment.website_file_id is not None
    }
    total_size = 0
    for index, remote_attachment in enumerate(remote_attachments):
        if index >= MAX_REVIEW_IMAGES_COUNT:
            stats.attachments_skipped += 1
            continue
        if not isinstance(remote_attachment, dict):
            stats.attachments_skipped += 1
            continue
        website_file_id = max(0, int(remote_attachment.get("website_file_id") or 0))
        if website_file_id <= 0:
            stats.attachments_skipped += 1
            continue
        app_attachment_id = max(0, int(remote_attachment.get("app_attachment_id") or 0))
        attachment = attachments_by_id.get(app_attachment_id) if app_attachment_id > 0 else None
        if attachment is None: attachment = attachments_by_website_file_id.get(website_file_id)
        if attachment is not None:
            if attachment.review_id != review.id:
                stats.attachments_skipped += 1
                continue
            moderation_status = _attachment_status(review)
            if (attachment.website_file_id != website_file_id or attachment.moderation_status != moderation_status):
                attachment.website_file_id = website_file_id
                attachment.moderation_status = moderation_status
                stats.attachments_linked += 1
            continue

        downloaded = await _download_website_attachment(remote_attachment)
        if downloaded is None:
            stats.attachments_skipped += 1
            continue
        filename, mime_type, content = downloaded
        total_size += len(content)
        if total_size > MAX_REVIEW_TOTAL_SIZE_BYTES:
            stats.attachments_skipped += 1
            continue
        saved_path = await save_review_attachment_file(review.id, filename=filename, content=content)
        created_files.append(saved_path)
        attachment = ReviewAttachment(
            review_id=review.id,
            filename=filename,
            mime_type=mime_type,
            website_file_id=website_file_id,
            moderation_status=_attachment_status(review),
        )
        db.add(attachment)
        review.attachments.append(attachment)
        attachments_by_website_file_id[website_file_id] = attachment
        stats.attachments_imported += 1
