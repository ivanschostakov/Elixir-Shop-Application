from datetime import timedelta
from hashlib import sha256

from fastapi import BackgroundTasks, HTTPException, Request
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from config import EMAIL_VERIFICATION_MAX_ATTEMPTS, EMAIL_VERIFICATION_CODE_TTL_MINUTES, ufa_now
from src.app.services.email_verification import (
    EmailVerificationConfigError,
    EmailVerificationDeliveryError,
    generate_email_verification_code,
    hash_email_verification_code,
    send_user_password_reset_code_email,
    verify_email_verification_code,
)
from src.app.services.rate_limit import enforce_rate_limit
from src.app.services.security import hash_password
from src.database.models import EmailVerificationCode, User, UserPasswordReset, UserSession
from .common import logger


def _invalid_code() -> HTTPException:
    return HTTPException(400, detail={"code": "invalid_reset_code", "message": "Invalid or expired verification code"})


def _password_fingerprint(user: User) -> str:
    return sha256(user.password_hash.encode()).hexdigest()


async def _active_verified_user(db: AsyncSession, email: str) -> User | None:
    return (await db.execute(
        select(User).where(User.email == email, User.is_active.is_(True), User.is_verified.is_(True)).with_for_update()
    )).scalar_one_or_none()


async def _deliver_code(email: str, code: str, user_id: int) -> None:
    try:
        await send_user_password_reset_code_email(to_email=email, code=code)
    except (EmailVerificationConfigError, EmailVerificationDeliveryError):
        logger.exception("Failed to send customer password reset code user_id=%s", user_id)


async def request_password_reset(db: AsyncSession, request: Request, tasks: BackgroundTasks, *, email: str) -> None:
    await enforce_rate_limit(request, scope="auth:password_reset:request", limit=15, window_seconds=900)
    await enforce_rate_limit(request, scope="auth:password_reset:email", limit=3, window_seconds=900, key=email)
    user = await _active_verified_user(db, email)
    # Make the same expensive hash for unknown addresses and send mail outside the response.
    code = generate_email_verification_code()
    code_hash = hash_email_verification_code(code)
    if user is None:
        return

    pending = await db.get(UserPasswordReset, user.id)
    if pending is None:
        pending = UserPasswordReset(user_id=user.id)
        db.add(pending)
    pending.email = email
    pending.code_hash = code_hash
    pending.password_fingerprint = _password_fingerprint(user)
    pending.expires_at = ufa_now() + timedelta(minutes=EMAIL_VERIFICATION_CODE_TTL_MINUTES)
    pending.attempt_count = 0
    await db.commit()
    tasks.add_task(_deliver_code, email, code, user.id)


async def confirm_password_reset(db: AsyncSession, request: Request, *, email: str, code: str, password: str) -> None:
    await enforce_rate_limit(request, scope="auth:password_reset:confirm", limit=20, window_seconds=900)
    user = await _active_verified_user(db, email)
    if user is None:
        raise _invalid_code()
    pending = await db.get(UserPasswordReset, user.id)
    now = ufa_now()
    if (
        pending is None or pending.email != email or pending.expires_at <= now
        or pending.attempt_count >= EMAIL_VERIFICATION_MAX_ATTEMPTS
        or pending.password_fingerprint != _password_fingerprint(user)
    ):
        raise _invalid_code()
    if not verify_email_verification_code(code, pending.code_hash):
        pending.attempt_count += 1
        await db.commit()
        raise _invalid_code()

    user.password_hash = hash_password(password)
    user.app_password_reset_at = now
    await db.delete(pending)
    await db.execute(update(UserSession).where(
        UserSession.user_id == user.id, UserSession.purpose == "app", UserSession.revoked_at.is_(None),
    ).values(revoked_at=now))
    await db.execute(update(EmailVerificationCode).where(
        EmailVerificationCode.user_id == user.id, EmailVerificationCode.used_at.is_(None),
    ).values(used_at=now))
    await db.commit()
