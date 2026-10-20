from datetime import timedelta
from typing import Any
from uuid import uuid4
from config import TELEGRAM_COMMUNITY_PROFILE_CACHE_SECONDS, ufa_now
from src.app.services.community import COMMUNITY_AVATARS_DIR
from src.database.models import CommunityMessage
from .common import _APP_HEADER_SUFFIXES, log


def _telethon_author_snapshot(sender: Any, telegram_message_id: int) -> tuple[str, int, str]:
    from telethon import utils

    if sender is None: return "user", -telegram_message_id, "Telegram member"
    title = str(getattr(sender, "title", "") or "").strip()
    if title: return "chat", int(utils.get_peer_id(sender) or -telegram_message_id), title
    peer_id = int(utils.get_peer_id(sender) or -telegram_message_id)
    full_name = " ".join(str(getattr(sender, key, "") or "").strip() for key in ("first_name", "last_name")).strip() or "Telegram member"
    return "user", peer_id, full_name


def _app_header_author_name(header: str) -> str | None:
    for suffix in _APP_HEADER_SUFFIXES:
        if header.endswith(suffix): return header[: -len(suffix)].strip() or None
    return None


def _telethon_message_text(message: Any, logical: CommunityMessage | None = None) -> str:
    value = str(getattr(message, "message", "") or "")
    header, separator, body = value.partition("\n\n")
    if separator and ((logical is not None and logical.source == "app") or _app_header_author_name(header) is not None): return body
    return value


def _archived_app_author_name(message: Any) -> str | None:
    header = str(getattr(message, "message", "") or "").partition("\n\n")[0]
    return _app_header_author_name(header)


async def _refresh_telethon_author_avatar(client: Any, sender: Any, author: Any) -> None:
    if sender is None: return
    now = ufa_now()
    stale = author.avatar_file_id is None or (author.avatar_refreshed_at is None or author.avatar_refreshed_at < now - timedelta(seconds=TELEGRAM_COMMUNITY_PROFILE_CACHE_SECONDS))
    if not stale: return
    author.avatar_refreshed_at = now
    filename = f"telethon-{author.kind}-{author.telegram_peer_id}-{uuid4().hex}.jpg"
    target = COMMUNITY_AVATARS_DIR / filename
    try:
        downloaded = await client.download_profile_photo(sender, file=str(target), download_big=True)
        if downloaded and target.exists():
            if author.avatar_local_filename: (COMMUNITY_AVATARS_DIR / author.avatar_local_filename).unlink(missing_ok=True)
            author.avatar_file_id = f"telethon:{author.telegram_peer_id}"
            author.avatar_local_filename = filename
        else:
            target.unlink(missing_ok=True)
            author.avatar_file_id = "telethon:none"
    except Exception:
        target.unlink(missing_ok=True)
        author.avatar_file_id = "telethon:error"
        log.info("telethon author avatar refresh skipped peer_id=%s", author.telegram_peer_id)
