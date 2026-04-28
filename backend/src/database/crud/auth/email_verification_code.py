from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config import ufa_now
from src.database.models.auth.email_verification_code import EmailVerificationCode


async def create_email_verification_code(
    session: AsyncSession,
    *,
    user_id: int,
    code_hash: str,
    expires_at: datetime,
    commit: bool = True,
) -> EmailVerificationCode:
    verification_code = EmailVerificationCode(user_id=user_id, code_hash=code_hash, expires_at=expires_at)
    session.add(verification_code)
    if commit:
        await session.commit()
    else:
        await session.flush()
    await session.refresh(verification_code)
    return verification_code


async def get_latest_pending_email_verification_code(session: AsyncSession, *, user_id: int) -> EmailVerificationCode | None:
    stmt = (
        select(EmailVerificationCode)
        .where(
            EmailVerificationCode.user_id == user_id,
            EmailVerificationCode.used_at.is_(None),
            EmailVerificationCode.expires_at > ufa_now(),
        )
        .order_by(EmailVerificationCode.id.desc())
        .limit(1)
    )
    return (await session.execute(stmt)).scalar_one_or_none()
