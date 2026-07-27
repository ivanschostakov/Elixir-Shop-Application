from __future__ import annotations

import hashlib
import hmac
import json
import logging
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config import (
    WEBSITE_REVIEW_SYNC_ENDPOINT,
    WEBSITE_REVIEW_SYNC_SECRET,
    WEBSITE_REVIEW_SYNC_TIMEOUT_SECONDS,
)
from src.database.models import Product, Review, User


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


async def _pull_website_reviews(
    db: AsyncSession,
    client: WebsiteReviewSyncClient,
    stats: WebsiteReviewSyncStats,
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

        remote_ids = [int(row["remote_id"]) for row in rows if str(row.get("remote_id") or "").isdigit()]
        existing_reviews = list(
            (
                await db.execute(select(Review).where(Review.website_review_id.in_(remote_ids)))
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
                    **values,
                )
                db.add(review)
                existing_by_remote_id[remote_id] = review
                stats.imported += 1
                continue

            if (
                remote_updated_at is not None
                and review.website_updated_at is not None
                and remote_updated_at <= review.website_updated_at
            ):
                continue
            local_updated_at = review.updated_at
            if (
                remote_updated_at is not None
                and local_updated_at is not None
                and remote_updated_at < local_updated_at
                and review.website_updated_at is not None
                and local_updated_at > review.website_updated_at
            ):
                stats.conflicts += 1
                continue

            changed = any(getattr(review, key) != value for key, value in values.items())
            if changed:
                for key, value in values.items():
                    setattr(review, key, value)
                review.product_id = product.id
                stats.updated_from_website += 1
            review.website_updated_at = remote_updated_at

        await db.flush()
        offset += len(rows)
        if len(rows) < PAGE_SIZE:
            break


async def _push_app_reviews(
    db: AsyncSession,
    client: WebsiteReviewSyncClient,
    stats: WebsiteReviewSyncStats,
) -> None:
    offset = 0
    while True:
        rows = (
            await db.execute(
                select(Review, Product.system_id, User.email, User.name, User.surname)
                .join(Product, Product.id == Review.product_id)
                .outerjoin(User, User.id == Review.user_id)
                .where(Product.system_id.is_not(None))
                .order_by(Review.id)
                .offset(offset)
                .limit(PAGE_SIZE)
            )
        ).all()
        if not rows:
            break

        payload: list[dict[str, Any]] = []
        for review, system_id, email, name, surname in rows:
            author_name = f"{name or ''} {surname or ''}".strip() or review.guest_name or "Покупатель из приложения"
            payload.append(
                {
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
                    "created_at": _iso(review.created_at),
                    "updated_at": _iso(review.updated_at),
                }
            )
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
            remote_id = int(result.get("remote_id") or 0)
            if remote_id > 0:
                review.website_review_id = remote_id
            review.website_updated_at = _parse_datetime(result.get("updated_at")) or review.website_updated_at
            outcome = str(result.get("outcome") or "")
            if outcome == "created":
                stats.created_on_website += 1
            elif outcome == "updated":
                stats.updated_on_website += 1
            elif outcome == "conflict":
                stats.conflicts += 1
            stats.pushed += 1
        await db.flush()
        offset += len(rows)
        if len(rows) < PAGE_SIZE:
            break


async def sync_reviews_with_website(db: AsyncSession) -> WebsiteReviewSyncStats:
    client = WebsiteReviewSyncClient()
    stats = WebsiteReviewSyncStats()
    await _pull_website_reviews(db, client, stats)
    await _push_app_reviews(db, client, stats)
    await db.commit()
    log.info("Website review sync completed: %s", stats.as_dict())
    return stats


__all__ = [
    "WebsiteReviewSyncClient",
    "WebsiteReviewSyncStats",
    "sync_reviews_with_website",
    "website_review_sync_configured",
]
