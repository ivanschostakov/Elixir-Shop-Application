import hashlib
import hmac
import time
from pathlib import Path
from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession
from config import TELEGRAM_BOT_TOKEN, TELEGRAM_COMMUNITY_MEDIA_SIGNING_SECRET
from src.database.models import CommunityAttachment, CommunityAuthor
from .common import COMMUNITY_ATTACHMENTS_DIR, COMMUNITY_AVATARS_DIR, COMMUNITY_GROUP_DIR


def _media_secret() -> bytes:
    value = TELEGRAM_COMMUNITY_MEDIA_SIGNING_SECRET or TELEGRAM_BOT_TOKEN or "community-media-disabled"
    return value.encode("utf-8")


def _media_signature(*, media_type: str, media_id: int, user_id: int, expires: int) -> str:
    payload = f"{media_type}:{media_id}:{user_id}:{expires}".encode("utf-8")
    return hmac.new(_media_secret(), payload, hashlib.sha256).hexdigest()


def build_community_media_url(request: Request, *, media_type: str, media_id: int, user_id: int) -> str:
    expires = int(time.time()) + 900
    signature = _media_signature(media_type=media_type, media_id=media_id, user_id=user_id, expires=expires)
    return str(request.url_for("get_community_media", media_type=media_type, media_id=media_id).include_query_params(uid=user_id, expires=expires, signature=signature))


def verify_community_media_signature(*, media_type: str, media_id: int, user_id: int, expires: int, signature: str) -> bool:
    if expires < int(time.time()): return False
    expected = _media_signature(media_type=media_type, media_id=media_id, user_id=user_id, expires=expires)
    return hmac.compare_digest(signature, expected)


async def resolve_community_media_path(db: AsyncSession, *, media_type: str, media_id: int) -> tuple[Path, str | None] | None:
    if media_type == "author":
        author = await db.get(CommunityAuthor, media_id)
        return (COMMUNITY_AVATARS_DIR / author.avatar_local_filename, "image/jpeg") if author and author.avatar_local_filename else None
    if media_type == "attachment":
        attachment = await db.get(CommunityAttachment, media_id)
        return (COMMUNITY_ATTACHMENTS_DIR / attachment.local_filename, attachment.mime_type) if attachment and attachment.local_filename else None
    if media_type == "group" and media_id == 0:
        path = COMMUNITY_GROUP_DIR / "avatar"
        return (path, "image/jpeg") if path.exists() else None
    return None


def _safe_filename(value: str | None, fallback: str) -> str:
    normalized = Path((value or "").strip()).name
    return normalized[:255] or fallback
