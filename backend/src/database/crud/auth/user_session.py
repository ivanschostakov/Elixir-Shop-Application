from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config import ufa_now

from src.database.models import UserSession
from src.database.schemas import UserSessionCreate, UserSessionUpdate


async def create_user_session(session: AsyncSession, data: UserSessionCreate) -> UserSession:
    session_obj = UserSession(**data.model_dump(exclude_none=True))
    session.add(session_obj)
    await session.commit()
    await session.refresh(session_obj)
    return session_obj


async def get_user_session_by_id(session: AsyncSession, user_session_id: int) -> UserSession | None:
    return (await session.execute(select(UserSession).where(UserSession.id == user_session_id))).scalar_one_or_none()


async def get_user_session_by_refresh_token_hash(session: AsyncSession, refresh_token_hash: str) -> UserSession | None:
    return (await session.execute(select(UserSession).where(UserSession.refresh_token_hash == refresh_token_hash))).scalar_one_or_none()


async def get_user_sessions(session: AsyncSession, *, user_id: int | None = None, is_revoked: bool | None = None, is_expired: bool | None = None, offset: int = 0, limit: int = 100) -> list[UserSession]:
    stmt = select(UserSession)
    if user_id is not None: stmt = stmt.where(UserSession.user_id == user_id)
    if is_revoked: stmt = stmt.where(UserSession.revoked_at.is_not(None))
    if is_revoked is False: stmt = stmt.where(UserSession.revoked_at.is_(None))
    if is_expired: stmt = stmt.where(UserSession.expires_at < ufa_now())
    if is_expired is False: stmt = stmt.where(UserSession.expires_at >= ufa_now())
    stmt = stmt.order_by(UserSession.id.desc()).offset(offset).limit(limit)
    return list((await session.execute(stmt)).scalars().all())


async def update_user_session(session: AsyncSession, user_session: UserSession, data: UserSessionUpdate) -> UserSession:
    for field, value in data.model_dump(exclude_unset=True).items(): setattr(user_session, field, value)
    await session.commit()
    await session.refresh(user_session)
    return user_session


async def revoke_user_session(session: AsyncSession, user_session: UserSession, revoked_at: datetime | None = None) -> UserSession:
    user_session.revoked_at = revoked_at or ufa_now()
    await session.commit()
    await session.refresh(user_session)
    return user_session


async def delete_user_session(session: AsyncSession, user_session: UserSession) -> None:
    await session.delete(user_session)
    await session.commit()
