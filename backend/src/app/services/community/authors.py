from datetime import timedelta
from uuid import uuid4
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from config import TELEGRAM_COMMUNITY_MAX_DOWNLOAD_BYTES, TELEGRAM_COMMUNITY_PROFILE_CACHE_SECONDS, ufa_now
from src.database.models import CommunityAuthor
from src.integrations.telegram import TelegramBotAPIError, TelegramBotClient, get_telegram_bot_client
from .common import COMMUNITY_AVATARS_DIR, log


async def _upsert_author(db: AsyncSession, *, kind: str, telegram_peer_id: int, full_name: str, app_user_id: int | None = None, telegram_client: TelegramBotClient | None = None, refresh_avatar: bool = True) -> CommunityAuthor:
    author = (await db.execute(select(CommunityAuthor).where(CommunityAuthor.kind == kind, CommunityAuthor.telegram_peer_id == telegram_peer_id))).scalar_one_or_none()
    if author is None:
        author = CommunityAuthor(kind=kind, telegram_peer_id=telegram_peer_id, app_user_id=app_user_id, full_name=full_name or "Telegram member")
        db.add(author); await db.flush()
    else:
        author.full_name = full_name or author.full_name
        if app_user_id: author.app_user_id = app_user_id
    now = ufa_now()
    stale = author.avatar_refreshed_at is None or author.avatar_refreshed_at < now - timedelta(seconds=TELEGRAM_COMMUNITY_PROFILE_CACHE_SECONDS)
    if stale and refresh_avatar:
        author.avatar_refreshed_at = now
        try:
            client = telegram_client or get_telegram_bot_client()
            photo = await client.get_user_profile_photo(telegram_peer_id) if kind == "user" else (await client.get_chat(telegram_peer_id)).get("photo")
            file_id = str((photo or {}).get("file_id") or (photo or {}).get("big_file_id") or (photo or {}).get("small_file_id") or "")
            if file_id and file_id != author.avatar_file_id:
                filename = f"{kind}-{telegram_peer_id}-{uuid4().hex}"
                await client.download_file(file_id, COMMUNITY_AVATARS_DIR / filename, max_bytes=TELEGRAM_COMMUNITY_MAX_DOWNLOAD_BYTES)
                if author.avatar_local_filename: (COMMUNITY_AVATARS_DIR / author.avatar_local_filename).unlink(missing_ok=True)
                author.avatar_file_id = file_id; author.avatar_local_filename = filename
        except (TelegramBotAPIError, TimeoutError, OSError): log.info("community author avatar refresh skipped peer_id=%s", telegram_peer_id)
    return author
