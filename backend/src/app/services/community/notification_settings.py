from fastapi import HTTPException
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from config import TELEGRAM_COMMUNITY_CHAT_ID
from src.database.models import CommunityNotificationMute, CommunityTopic, User
from src.database.schemas.community import CommunityNotificationSettingsRead


async def get_community_notification_settings(db: AsyncSession, *, user: User) -> CommunityNotificationSettingsRead:
    rows = list((await db.execute(select(CommunityNotificationMute.topic_id).where(
        CommunityNotificationMute.user_id == user.id,
        CommunityNotificationMute.telegram_chat_id == TELEGRAM_COMMUNITY_CHAT_ID,
    ))).scalars().all())
    return CommunityNotificationSettingsRead(muted=None in rows, muted_topic_ids=sorted(topic_id for topic_id in rows if topic_id is not None))


async def set_community_notification_muted(db: AsyncSession, *, user: User, muted: bool, topic_id: int | None = None) -> CommunityNotificationSettingsRead:
    if not TELEGRAM_COMMUNITY_CHAT_ID:
        raise HTTPException(404, "Community is unavailable")
    # Serialize concurrent switches from different devices and duplicate requests.
    await db.execute(select(User.id).where(User.id == user.id).with_for_update())
    if topic_id is not None:
        topic = await db.get(CommunityTopic, topic_id)
        if topic is None or topic.telegram_chat_id != TELEGRAM_COMMUNITY_CHAT_ID or topic.is_deleted or topic.is_hidden:
            raise HTTPException(404, "Community topic not found")
    scope = (CommunityNotificationMute.user_id == user.id,
        CommunityNotificationMute.telegram_chat_id == TELEGRAM_COMMUNITY_CHAT_ID,
        CommunityNotificationMute.topic_id == topic_id)
    if muted:
        existing = (await db.execute(select(CommunityNotificationMute.id).where(*scope))).scalar_one_or_none()
        if existing is None:
            db.add(CommunityNotificationMute(user_id=user.id, telegram_chat_id=TELEGRAM_COMMUNITY_CHAT_ID, topic_id=topic_id))
    else:
        await db.execute(delete(CommunityNotificationMute).where(*scope))
    await db.commit()
    return await get_community_notification_settings(db, user=user)
