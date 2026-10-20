from datetime import timedelta
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status
from config import EMAIL_VERIFICATION_CODE_TTL_MINUTES, EMAIL_VERIFICATION_MAX_ATTEMPTS, ufa_now
from src.app.services.email_verification import generate_email_verification_code, hash_email_verification_code, send_user_verification_code_email, verify_email_verification_code
from src.database.crud.auth.email_verification_code import create_email_verification_code, get_latest_pending_email_verification_code
from src.database.models.auth.user import User


async def _create_and_send_verification_code(user: User, db: AsyncSession) -> None:
    if not user.email: raise RuntimeError("Cannot create an email verification code for a user without email")
    code = generate_email_verification_code()
    code_hash = hash_email_verification_code(code)
    expires_at = ufa_now() + timedelta(minutes=EMAIL_VERIFICATION_CODE_TTL_MINUTES)
    await create_email_verification_code(db, user_id=user.id, code_hash=code_hash, expires_at=expires_at, commit=False)
    await send_user_verification_code_email(to_email=user.email, code=code)


async def _verify_latest_email_code(user: User, code: str, db: AsyncSession) -> None:
    verification_code = await get_latest_pending_email_verification_code(db, user_id=user.id)
    if verification_code is None or verification_code.attempt_count >= EMAIL_VERIFICATION_MAX_ATTEMPTS: raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired verification code")

    if not verify_email_verification_code(code, verification_code.code_hash):
        verification_code.attempt_count += 1
        await db.commit()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid verification code")

    verification_code.used_at = ufa_now()
