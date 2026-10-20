from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from config import API_BASE_URL, PUBLIC_API_BASE_URL
from src.database.models import Review, ReviewAttachment


def _parse_datetime(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip(): return None
    try: result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError: return None
    if result.tzinfo is None: return result.replace(tzinfo=timezone.utc)
    return result


def _iso(value: datetime | None) -> str | None:
    if value is None: return None
    if value.tzinfo is None: value = value.replace(tzinfo=timezone.utc)
    return value.isoformat()


def _mark_review_synced(review: Review, result: dict[str, Any]) -> None:
    remote_id = int(result.get("remote_id") or 0)
    if remote_id > 0: review.website_review_id = remote_id
    synced_at = _parse_datetime(result.get("updated_at")) or datetime.now(timezone.utc)
    # Review.updated_at has an automatic on-update value. Updating only the
    # website metadata would therefore make the review look locally modified
    # again and cause an endless push loop. Persist both timestamps explicitly
    # at the same remote checkpoint.
    review.website_updated_at = synced_at
    review.updated_at = synced_at


def _review_state(review: Review) -> str:
    if review.rejected_at is not None: return "rejected"
    return "published" if review.moderated else "pending"


def _remote_review_state(row: dict[str, Any]) -> tuple[bool, datetime | None, datetime | None]:
    updated_at = _parse_datetime(row.get("updated_at"))
    status = str(row.get("status") or "pending")
    if status == "published": return True, updated_at or datetime.now(timezone.utc), None
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


def _local_review_for_remote(row: dict[str, Any], *, product_id: int, existing_by_remote_id: dict[int, Review], existing_by_app_id: dict[int, Review]) -> Review | None:
    remote_id = max(0, int(row.get("remote_id") or 0))
    review = existing_by_remote_id.get(remote_id)
    if review is not None: return review

    app_review_id = max(0, int(row.get("app_review_id") or 0))
    review = existing_by_app_id.get(app_review_id)
    if review is None or review.product_id != product_id or review.website_review_id not in (None, remote_id): return None
    review.website_review_id = remote_id
    existing_by_remote_id[remote_id] = review
    return review


def _attachment_status(review: Review) -> str:
    if review.rejected_at is not None: return "rejected"
    return "approved" if review.moderated else "pending"


def _attachment_public_url(review: Review, attachment: ReviewAttachment) -> str:
    base_url = (PUBLIC_API_BASE_URL or API_BASE_URL).rstrip("/")
    if not base_url.startswith("https://"): raise RuntimeError("Public API URL must use HTTPS for review attachment synchronization")
    return f"{base_url}/media/reviews/{review.id}/{attachment.filename}"


def _push_payload(review: Review, *, system_id: UUID, email: str | None, name: str | None, surname: str | None) -> dict[str, Any]:
    author_name = "Анонимный покупатель" if getattr(review, "hide_sender_name", False) else f"{name or ''} {surname or ''}".strip() or review.guest_name or "Покупатель из приложения"
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
                "website_file_id": attachment.website_file_id,
                "url": _attachment_public_url(review, attachment),
                "filename": attachment.filename,
                "mime_type": attachment.mime_type,
            }
            for attachment in review.attachments
        ],
        "created_at": _iso(review.created_at),
        "updated_at": _iso(review.updated_at),
    }
