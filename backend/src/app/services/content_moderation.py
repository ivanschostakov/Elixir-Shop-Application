from __future__ import annotations

import hashlib
import re

from datetime import timedelta
from typing import Any

from fastapi import Request
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from config import ufa_now
from src.app.services.rate_limit import client_ip_from_request
from src.database.models import Review

PROFANITY_TERMS = {
    "бляд",
    "сука",
    "хуй",
    "пизд",
    "еба",
    "ебл",
    "fuck",
    "shit",
    "scam",
}

SPAM_TERMS = {
    "casino",
    "crypto",
    "forex",
    "viagra",
    "free money",
    "заработок",
    "казино",
    "ставки",
}

URL_PATTERN = re.compile(r"https?://|www\.", re.IGNORECASE)


def normalize_review_text(value: str | None) -> str:
    return re.sub(r"\s+", " ", (value or "").strip().lower())


def build_duplicate_group_key(*, product_id: int, user_id: int | None, guest_email: str | None, text: str | None) -> str:
    identity = str(user_id) if user_id is not None else (guest_email or "").strip().lower()
    raw = f"{product_id}|{identity}|{normalize_review_text(text)}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _contains_any(text: str, terms: set[str]) -> bool:
    return any(term in text for term in terms)


async def analyze_review_submission(
    db: AsyncSession,
    *,
    request: Request,
    product_id: int,
    user_id: int | None,
    guest_email: str | None,
    text: str | None,
) -> dict[str, Any]:
    normalized_text = normalize_review_text(text)
    submitter_ip = client_ip_from_request(request)
    duplicate_group_key = build_duplicate_group_key(product_id=product_id, user_id=user_id, guest_email=guest_email, text=text)
    duplicate_count = int((await db.execute(
        select(func.count(Review.id)).where(Review.duplicate_group_key == duplicate_group_key)
    )).scalar_one())
    recent_ip_count = 0
    if submitter_ip:
        recent_ip_count = int((await db.execute(
            select(func.count(Review.id)).where(
                Review.submitter_ip == submitter_ip,
                Review.created_at >= ufa_now() - timedelta(hours=24),
            )
        )).scalar_one())

    profanity_flag = _contains_any(normalized_text, PROFANITY_TERMS)
    spam_terms_flag = _contains_any(normalized_text, SPAM_TERMS)
    url_count = len(URL_PATTERN.findall(normalized_text))
    duplicate_flag = duplicate_count > 0
    suspicious_ip_flag = recent_ip_count >= 4
    spam_score = 0
    if spam_terms_flag:
        spam_score += 50
    if url_count:
        spam_score += min(40, url_count * 20)
    if duplicate_flag:
        spam_score += 30
    if suspicious_ip_flag:
        spam_score += 25
    if len(normalized_text) < 8:
        spam_score += 10
    spam_score = min(spam_score, 100)
    flags = {
        "spam_terms": spam_terms_flag,
        "profanity": profanity_flag,
        "duplicate": duplicate_flag,
        "suspicious_ip": suspicious_ip_flag,
        "url_count": url_count,
        "recent_ip_reviews_24h": recent_ip_count,
        "duplicate_count": duplicate_count,
    }
    return {
        "submitter_ip": submitter_ip,
        "duplicate_group_key": duplicate_group_key,
        "spam_score": spam_score,
        "profanity_flag": profanity_flag,
        "duplicate_flag": duplicate_flag,
        "suspicious_ip_flag": suspicious_ip_flag,
        "moderation_flags": flags,
    }
