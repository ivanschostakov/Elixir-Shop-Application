from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.models import ReferralProfile


async def list_referral_profiles(session: AsyncSession, *, limit: int, offset: int) -> list[ReferralProfile]:
    stmt = select(ReferralProfile).order_by(ReferralProfile.id.desc()).limit(limit).offset(offset)
    return list((await session.execute(stmt)).scalars().all())
