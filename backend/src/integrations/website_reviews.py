from __future__ import annotations

import hashlib
import hmac
import json
import logging
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit
from uuid import UUID

import httpx
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from config import (
    API_BASE_URL,
    PUBLIC_API_BASE_URL,
    WEBSITE_REVIEW_SYNC_ENDPOINT,
    WEBSITE_REVIEW_SYNC_SECRET,
    WEBSITE_REVIEW_SYNC_TIMEOUT_SECONDS,
)
from src.app.services.cache import get_cache_service
from src.app.services.review_attachments import (
    MAX_REVIEW_IMAGES_COUNT,
    MAX_REVIEW_IMAGE_SIZE_BYTES,
    MAX_REVIEW_TOTAL_SIZE_BYTES,
    build_review_attachment_filename,
    remove_review_attachment_file,
    save_review_attachment_file,
    validate_review_attachment,
)
from src.database.models import (
    Product,
    Review,
    ReviewAttachment,
    ReviewModerationEvent,
    User,
    Variant,
)


log = logging.getLogger("integrations.website_reviews")
PAGE_SIZE = 100


@dataclass
class WebsiteReviewSyncStats:
    pulled: int = 0
    imported: int = 0
    updated_from_website: int = 0
    skipped_missing_product: int = 0
    pushed: int = 0
    created_on_website: int = 0
    updated_on_website: int = 0
    conflicts: int = 0
    attachments_imported: int = 0
    attachments_linked: int = 0
    attachments_skipped: int = 0

    def as_dict(self) -> dict[str, int]:
        return asdict(self)


def website_review_sync_configured() -> bool:
    return bool(WEBSITE_REVIEW_SYNC_ENDPOINT and WEBSITE_REVIEW_SYNC_SECRET)


def _parse_datetime(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if result.tzinfo is None:
        return result.replace(tzinfo=timezone.utc)
    return result


def _iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.isoformat()


def _mark_review_synced(review: Review, result: dict[str, Any]) -> None:
    remote_id = int(result.get("remote_id") or 0)
    if remote_id > 0:
        review.website_review_id = remote_id
    synced_at = _parse_datetime(result.get("updated_at")) or datetime.now(timezone.utc)
    # Review.updated_at has an automatic on-update value. Updating only the
    # website metadata would therefore make the review look locally modified
    # again and cause an endless push loop. Persist both timestamps explicitly
    # at the same remote checkpoint.
    review.website_updated_at = synced_at
    review.updated_at = synced_at


class WebsiteReviewSyncClient:
    def __init__(self) -> None:
        if not website_review_sync_configured():
            raise RuntimeError("Website review sync is not configured")
        self.endpoint = WEBSITE_REVIEW_SYNC_ENDPOINT
        self.secret = WEBSITE_REVIEW_SYNC_SECRET.encode("utf-8")
        self.timeout = WEBSITE_REVIEW_SYNC_TIMEOUT_SECONDS

    async def request(self, action: str, payload: dict[str, Any]) -> dict[str, Any]:
        body = json.dumps({"action": action, **payload}, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        timestamp = str(int(time.time()))
        signature = hmac.new(self.secret, timestamp.encode("ascii") + b"." + body, hashlib.sha256).hexdigest()
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                self.endpoint,
                content=body,
                headers={
                    "Content-Type": "application/json",
                    "X-Elixir-Timestamp": timestamp,
                    "X-Elixir-Signature": signature,
                },
            )
        response.raise_for_status()
        result = response.json()
        if not isinstance(result, dict) or result.get("ok") is not True:
            raise RuntimeError(str(result.get("error") if isinstance(result, dict) else "Invalid review sync response"))
        return result


def _review_state(review: Review) -> str:
    if review.rejected_at is not None:
        return "rejected"
    return "published" if review.moderated else "pending"


def _remote_review_state(
    row: dict[str, Any],
) -> tuple[bool, datetime | None, datetime | None]:
    updated_at = _parse_datetime(row.get("updated_at"))
    status = str(row.get("status") or "pending")
    if status == "published":
        return True, updated_at or datetime.now(timezone.utc), None
    if status == "rejected":
        decision_at = updated_at or datetime.now(timezone.utc)
        return False, decision_at, decision_at
    return False, None, None


def _remote_values(row: dict[str, Any]) -> dict[str, Any]:
    moderated, moderated_at, rejected_at = _remote_review_state(row)
    return {
        "value": max(0, min(5, int(row.get("rating") or 0))),
        "text": str(row["text"]).strip() if row.get("text") else None,
        "answer": str(row["answer"]).strip() if row.get("answer") else None,
        "likes": max(0, int(row.get("likes") or 0)),
        "dislikes": max(0, int(row.get("dislikes") or 0)),
        "moderated": moderated,
        "moderated_at": moderated_at,
        "rejected_at": rejected_at,
        "guest_name": str(row["author_name"]).strip()[:120] if row.get("author_name") else "Покупатель с сайта",
        "guest_email": str(row["author_email"]).strip()[:320] if row.get("author_email") else None,
    }


def _attachment_status(review: Review) -> str:
    if review.rejected_at is not None:
        return "rejected"
    return "approved" if review.moderated else "pending"


def _attachment_public_url(review: Review, attachment: ReviewAttachment) -> str:
    base_url = (PUBLIC_API_BASE_URL or API_BASE_URL).rstrip("/")
    if not base_url.startswith("https://"):
        raise RuntimeError("Public API URL must use HTTPS for review attachment synchronization")
    return f"{base_url}/media/reviews/{review.id}/{attachment.filename}"


def _push_payload(
    review: Review,
    *,
    system_id: UUID,
    email: str | None,
    name: str | None,
    surname: str | None,
) -> dict[str, Any]:
    author_name = f"{name or ''} {surname or ''}".strip() or review.guest_name or "Покупатель из приложения"
    return {
        "app_review_id": review.id,
        "remote_id": review.website_review_id,
        "product_system_id": str(system_id),
        "rating": review.value,
        "text": review.text,
        "answer": review.answer,
        "likes": review.likes,
        "dislikes": review.dislikes,
        "status": _review_state(review),
        "author_name": author_name,
        "author_email": email or review.guest_email,
        "attachments": [
            {
                "app_attachment_id": attachment.id,
                "url": _attachment_public_url(review, attachment),
                "filename": attachment.filename,
                "mime_type": attachment.mime_type,
            }
            for attachment in review.attachments
        ],
        "created_at": _iso(review.created_at),
        "updated_at": _iso(review.updated_at),
    }


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


async def _download_website_attachment(
    row: dict[str, Any],
) -> tuple[str, str, bytes] | None:
    url = str(row.get("url") or "").strip()
    if not _valid_website_attachment_url(url):
        return None
    declared_size = max(0, int(row.get("size") or 0))
    if declared_size > MAX_REVIEW_IMAGE_SIZE_BYTES:
        return None
    async with httpx.AsyncClient(
        timeout=WEBSITE_REVIEW_SYNC_TIMEOUT_SECONDS,
        follow_redirects=False,
    ) as client:
        response = await client.get(url, headers={"Accept": "image/jpeg,image/png,image/webp"})
    if response.status_code == 404:
        return None
    response.raise_for_status()
    try:
        mime_type = validate_review_attachment(
            response.content,
            mime_type=response.headers.get("Content-Type") or str(row.get("mime_type") or ""),
        )
    except Exception:
        log.warning("Bitrix review attachment %s failed image validation", url)
        return None
    filename = build_review_attachment_filename(mime_type)
    return filename, mime_type, response.content


async def _sync_remote_attachments(
    db: AsyncSession,
    review: Review,
    row: dict[str, Any],
    stats: WebsiteReviewSyncStats,
    created_files: list[Path],
) -> None:
    remote_attachments = row.get("attachments")
    if not isinstance(remote_attachments, list):
        return
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
        if attachment is None:
            attachment = attachments_by_website_file_id.get(website_file_id)
        if attachment is not None:
            if attachment.review_id != review.id:
                stats.attachments_skipped += 1
                continue
            moderation_status = _attachment_status(review)
            if (
                attachment.website_file_id != website_file_id
                or attachment.moderation_status != moderation_status
            ):
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
        saved_path = await save_review_attachment_file(
            review.id,
            filename=filename,
            content=content,
        )
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


async def _pull_website_reviews(
    db: AsyncSession,
    client: WebsiteReviewSyncClient,
    stats: WebsiteReviewSyncStats,
    created_files: list[Path],
) -> None:
    offset = 0
    while True:
        response = await client.request("pull", {"offset": offset, "limit": PAGE_SIZE})
        rows = response.get("reviews")
        if not isinstance(rows, list):
            raise RuntimeError("Website review sync returned an invalid review list")
        if not rows:
            break

        product_keys: dict[str, UUID] = {}
        for row in rows:
            raw_key = str(row.get("product_system_id") or "")
            try:
                product_keys[raw_key] = UUID(raw_key)
            except ValueError:
                continue
        products = list(
            (
                await db.execute(select(Product).where(Product.system_id.in_(list(product_keys.values()))))
            ).scalars().all()
        ) if product_keys else []
        products_by_key = {str(product.system_id): product for product in products}
        missing_keys = {
            system_id
            for system_id in product_keys.values()
            if str(system_id) not in products_by_key
        }
        if missing_keys:
            variants = (
                await db.execute(
                    select(Variant, Product)
                    .join(Product, Product.id == Variant.product_id)
                    .where(Variant.system_id.in_(list(missing_keys)))
                )
            ).all()
            for variant, product in variants:
                products_by_key.setdefault(str(variant.system_id), product)

        remote_ids = [int(row["remote_id"]) for row in rows if str(row.get("remote_id") or "").isdigit()]
        existing_reviews = list(
            (
                await db.execute(
                    select(Review)
                    .options(selectinload(Review.attachments))
                    .where(Review.website_review_id.in_(remote_ids))
                )
            ).scalars().all()
        ) if remote_ids else []
        existing_by_remote_id = {int(review.website_review_id): review for review in existing_reviews if review.website_review_id}

        for row in rows:
            stats.pulled += 1
            remote_id = int(row.get("remote_id") or 0)
            product = products_by_key.get(str(row.get("product_system_id") or ""))
            if remote_id <= 0 or product is None:
                stats.skipped_missing_product += 1
                continue
            remote_updated_at = _parse_datetime(row.get("updated_at")) or _parse_datetime(row.get("created_at"))
            review = existing_by_remote_id.get(remote_id)
            values = _remote_values(row)
            if review is None:
                review = Review(
                    user_id=None,
                    product_id=product.id,
                    sync_origin="website",
                    website_review_id=remote_id,
                    website_updated_at=remote_updated_at,
                    created_at=_parse_datetime(row.get("created_at")) or datetime.now(timezone.utc),
                    updated_at=remote_updated_at or _parse_datetime(row.get("created_at")) or datetime.now(timezone.utc),
                    **values,
                )
                db.add(review)
                await db.flush()
                existing_by_remote_id[remote_id] = review
                stats.imported += 1
            else:
                previous_state = _review_state(review)
                previous_website_updated_at = review.website_updated_at
                remote_advanced = (
                    remote_updated_at is not None
                    and (
                        previous_website_updated_at is None
                        or remote_updated_at > previous_website_updated_at
                    )
                )
                local_conflict = (
                    remote_advanced
                    and previous_website_updated_at is not None
                    and review.updated_at is not None
                    and review.updated_at > previous_website_updated_at
                    and remote_updated_at is not None
                    and review.updated_at > remote_updated_at
                )
                authority_keys = {"answer", "moderated", "moderated_at", "rejected_at"}
                values_to_apply = (
                    {key: value for key, value in values.items() if key in authority_keys}
                    if local_conflict or not remote_advanced
                    else values
                )
                changed = any(
                    getattr(review, key) != value
                    for key, value in values_to_apply.items()
                )
                if changed:
                    for key, value in values_to_apply.items():
                        setattr(review, key, value)
                    review.product_id = product.id
                    stats.updated_from_website += 1
                if local_conflict:
                    stats.conflicts += 1
                if remote_advanced:
                    review.website_updated_at = remote_updated_at
                if (
                    remote_updated_at is not None
                    and remote_advanced
                    and not local_conflict
                ):
                    review.updated_at = remote_updated_at
                current_state = _review_state(review)
                if current_state != previous_state:
                    action = {
                        "published": "review.publish",
                        "rejected": "review.reject",
                        "pending": "review.restore",
                    }[current_state]
                    db.add(ReviewModerationEvent(
                        review_id=review.id,
                        actor_user_id=None,
                        action=action,
                        before_json={"status": previous_state},
                        after_json={"status": current_state},
                        metadata_json={
                            "source": "bitrix",
                            "website_review_id": remote_id,
                        },
                    ))

            await _sync_remote_attachments(
                db,
                review,
                row,
                stats,
                created_files,
            )

        await db.flush()
        offset += len(rows)
        if len(rows) < PAGE_SIZE:
            break


async def _push_app_reviews(
    db: AsyncSession,
    client: WebsiteReviewSyncClient,
    stats: WebsiteReviewSyncStats,
) -> None:
    last_review_id = 0
    while True:
        rows = (
            await db.execute(
                select(Review, Product.system_id, User.email, User.name, User.surname)
                .options(selectinload(Review.attachments))
                .join(Product, Product.id == Review.product_id)
                .outerjoin(User, User.id == Review.user_id)
                .where(Product.system_id.is_not(None))
                .where(Review.id > last_review_id)
                .where(
                    or_(
                        Review.website_review_id.is_(None),
                        Review.website_updated_at.is_(None),
                        Review.updated_at > Review.website_updated_at,
                    )
                )
                .order_by(Review.id)
                .limit(PAGE_SIZE)
            )
        ).all()
        if not rows:
            break

        await _push_rows(db, client, stats, rows)
        last_review_id = rows[-1][0].id
        if len(rows) < PAGE_SIZE:
            break


async def _push_rows(
    db: AsyncSession,
    client: WebsiteReviewSyncClient,
    stats: WebsiteReviewSyncStats,
    rows: list[Any],
) -> None:
    payload = [
        _push_payload(
            review,
            system_id=system_id,
            email=email,
            name=name,
            surname=surname,
        )
        for review, system_id, email, name, surname in rows
    ]
    response = await client.request("push", {"reviews": payload})
    results = response.get("results")
    if not isinstance(results, list):
        raise RuntimeError("Website review sync returned invalid push results")
    reviews_by_id = {review.id: review for review, *_ in rows}
    for result in results:
        app_review_id = int(result.get("app_review_id") or 0)
        review = reviews_by_id.get(app_review_id)
        if review is None:
            continue
        _mark_review_synced(review, result)
        outcome = str(result.get("outcome") or "")
        if outcome == "created":
            stats.created_on_website += 1
        elif outcome == "updated":
            stats.updated_on_website += 1
        elif outcome == "conflict":
            stats.conflicts += 1
        stats.pushed += 1
    await db.flush()


async def push_review_to_website(
    db: AsyncSession,
    *,
    review_id: int,
) -> WebsiteReviewSyncStats:
    if not website_review_sync_configured():
        raise RuntimeError("Website review sync is not configured")
    row = (
        await db.execute(
            select(Review, Product.system_id, User.email, User.name, User.surname)
            .options(selectinload(Review.attachments))
            .join(Product, Product.id == Review.product_id)
            .outerjoin(User, User.id == Review.user_id)
            .where(Review.id == review_id, Product.system_id.is_not(None))
            .execution_options(populate_existing=True)
        )
    ).one_or_none()
    if row is None:
        raise RuntimeError("Review product mapping is missing")
    stats = WebsiteReviewSyncStats()
    await _push_rows(db, WebsiteReviewSyncClient(), stats, [row])
    await db.commit()
    return stats


async def push_review_to_website_safely(
    db: AsyncSession,
    *,
    review_id: int,
) -> bool:
    if not website_review_sync_configured():
        log.warning(
            "Review %s was saved locally; website review sync is not configured",
            review_id,
        )
        return False
    try:
        await push_review_to_website(db, review_id=review_id)
        return True
    except Exception:
        await db.rollback()
        log.exception(
            "Review %s was saved locally but immediate Bitrix delivery failed; "
            "the sync worker will retry",
            review_id,
        )
        return False


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
        for file_path in created_files:
            remove_review_attachment_file(file_path)
        raise
    if (
        stats.imported
        or stats.updated_from_website
        or stats.attachments_imported
        or stats.attachments_linked
    ):
        cache = get_cache_service()
        await cache.bump_namespace("reviews")
        await cache.bump_namespace("product")
        await cache.bump_namespace("catalog")
    log.info("Website review sync completed: %s", stats.as_dict())
    return stats


__all__ = [
    "WebsiteReviewSyncClient",
    "WebsiteReviewSyncStats",
    "push_review_to_website",
    "push_review_to_website_safely",
    "sync_reviews_with_website",
    "website_review_sync_configured",
]
