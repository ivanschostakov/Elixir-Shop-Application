from typing import Any
from fastapi import HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status
from config import TELEGRAM_BOT_TOKEN, TELEGRAM_BOT_USERNAME, TELEGRAM_COMMUNITY_CHAT_ID, TELEGRAM_COMMUNITY_ENABLED, TELEGRAM_COMMUNITY_JOIN_URL, TELEGRAM_COMMUNITY_MAX_DOWNLOAD_BYTES
from src.database.schemas.community import CommunityGroupRead, CommunityStatusRead
from src.app.services.cache import get_cache_service
from src.database.models import User
from src.integrations.telegram import TelegramBotAPIError, TelegramBotClient, get_telegram_bot_client
from .common import COMMUNITY_GROUP_DIR, log
from .media import build_community_media_url


def _membership_cache_key(telegram_user_id: int) -> str:
    return f"telegram:community:membership:{TELEGRAM_COMMUNITY_CHAT_ID}:{telegram_user_id}"


async def invalidate_community_membership(telegram_user_id: int) -> None:
    client = get_cache_service().client
    if client is not None:
        try: await client.delete(_membership_cache_key(telegram_user_id))
        except Exception: log.exception("community membership cache invalidation failed")


def _is_active_member(member: dict[str, Any]) -> bool:
    member_status = str(member.get("status") or "")
    if member_status in {"creator", "administrator", "member"}: return True
    return member_status == "restricted" and bool(member.get("is_member"))


async def _membership_access(user: User, *, refresh: bool = False, telegram_client: TelegramBotClient | None = None) -> str:
    del user, refresh, telegram_client
    if not TELEGRAM_COMMUNITY_ENABLED or not TELEGRAM_COMMUNITY_CHAT_ID or not (TELEGRAM_BOT_TOKEN or "").strip(): return "temporarily_unavailable"
    # The app community is app-native. Telegram is a transport/mirror and never
    # an identity or membership prerequisite for an authenticated app user.
    return "granted"


def _action_url(access: str) -> str | None:
    if access == "telegram_link_required" and TELEGRAM_BOT_USERNAME: return f"https://t.me/{TELEGRAM_BOT_USERNAME}?start=link"
    if access == "membership_required": return TELEGRAM_COMMUNITY_JOIN_URL
    return None


async def get_community_status(db: AsyncSession, *, user: User, request: Request, refresh: bool = False, telegram_client: TelegramBotClient | None = None) -> CommunityStatusRead:
    access = await _membership_access(user, refresh=refresh, telegram_client=telegram_client)
    group: CommunityGroupRead | None = None
    if TELEGRAM_COMMUNITY_ENABLED and TELEGRAM_COMMUNITY_CHAT_ID:
        title = "Our Group"
        try:
            info = await (telegram_client or get_telegram_bot_client()).get_chat(TELEGRAM_COMMUNITY_CHAT_ID)
            title = str(info.get("title") or title)
            photo = info.get("photo") if isinstance(info.get("photo"), dict) else None
            file_id = str(photo.get("big_file_id") or photo.get("small_file_id") or "") if photo else ""
            group_path = COMMUNITY_GROUP_DIR / "avatar"
            if file_id and not group_path.exists(): await (telegram_client or get_telegram_bot_client()).download_file(file_id, group_path, max_bytes=TELEGRAM_COMMUNITY_MAX_DOWNLOAD_BYTES)
        except (TelegramBotAPIError, TimeoutError, OSError):
            pass
        group_path = COMMUNITY_GROUP_DIR / "avatar"
        group = CommunityGroupRead(title=title, image_url=build_community_media_url(request, media_type="group", media_id=0, user_id=user.id) if group_path.exists() else None)
    return CommunityStatusRead(enabled=TELEGRAM_COMMUNITY_ENABLED, access=access, group=group, action_url=_action_url(access))


async def require_community_access(user: User, *, telegram_client: TelegramBotClient | None = None) -> None:
    access = await _membership_access(user, telegram_client=telegram_client)
    if access != "granted":
        http_status = status.HTTP_503_SERVICE_UNAVAILABLE if access == "temporarily_unavailable" else status.HTTP_403_FORBIDDEN
        raise HTTPException(status_code=http_status, detail={"code": access, "message": "The community is temporarily unavailable"})
