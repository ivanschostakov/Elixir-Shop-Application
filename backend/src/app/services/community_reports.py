from fastapi import HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.app.services import community
from src.app.services.rate_limit import enforce_rate_limit
from src.database.models import CommunityAuthor, CommunityMessage, CommunityReport, CommunityTopic, User
from src.database.schemas.community import CommunityReportPayload, CommunityReportReceipt


async def report_community_message(db: AsyncSession, *, user: User, request: Request, topic_id: int, message_id: int, payload: CommunityReportPayload) -> CommunityReportReceipt:
    await community.require_community_access(user)
    await enforce_rate_limit(request, scope="community-report", limit=20, window_seconds=3600, key=str(user.id))
    # Serialise retries and account erasure against the same account.
    active = (await db.execute(select(User.id).where(User.id == user.id, User.is_active.is_(True)).with_for_update())).scalar_one_or_none()
    if active is None:
        raise HTTPException(401, "Account no longer available")
    message = (await db.execute(
        select(CommunityMessage).join(CommunityTopic)
        .where(CommunityMessage.id == message_id, CommunityMessage.topic_id == topic_id,
               CommunityTopic.telegram_chat_id == community.TELEGRAM_COMMUNITY_CHAT_ID,
               CommunityTopic.is_hidden.is_(False), CommunityTopic.is_deleted.is_(False))
        .with_for_update(of=CommunityMessage)
    )).scalar_one_or_none()
    if message is None:
        raise HTTPException(404, "Community message not found")
    existing = (await db.execute(select(CommunityReport).where(CommunityReport.reporter_id == user.id, CommunityReport.message_id == message_id))).scalar_one_or_none()
    if existing:
        return CommunityReportReceipt(id=existing.id, status=existing.status)
    if message.deleted_at:
        raise HTTPException(404, "Community message not found")
    author = await db.get(CommunityAuthor, message.author_id) if message.author_id else None
    if message.app_user_id == user.id or (author and author.app_user_id == user.id):
        raise HTTPException(422, "You cannot report your own message")
    report = CommunityReport(reporter_id=user.id, message_id=message.id, reason=payload.reason, details=payload.details.strip())
    db.add(report)
    await db.commit()
    return CommunityReportReceipt(id=report.id, status=report.status)
