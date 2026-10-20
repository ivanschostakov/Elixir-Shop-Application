from fastapi import HTTPException, Request
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status
from config import AUTH_LOGIN_ADMIN_BYPASS_EMAIL_2FA
from src.app.modules.auth.schemas.login import UserLoginPayload, UserLoginVerifyPayload
from src.app.modules.auth.schemas.register import UserRegisterPayload, UserRegisterVerifyPayload, UserRegistrationStartedResponse, UserVerificationCodeResendPayload, UserVerificationCodeSentResponse
from src.app.modules.auth.schemas.responses import AuthTokensWithUserResponse, AuthVerificationRequiredResponse
from src.app.services.email_verification import EmailVerificationConfigError, EmailVerificationDeliveryError
from src.app.services.security import hash_password
from src.database.crud.auth.admin import is_admin_user
from src.database.crud.auth.user import create_user, get_user_by_email
from src.database.schemas.auth.user import UserCreate
from src.normalize import optional_str
from .common import logger
from .rate_limits import _apply_auth_rate_limit
from .sessions import _build_auth_tokens_response
from .verification import _create_and_send_verification_code, _verify_latest_email_code
from .login import _get_login_user, _is_app_review_identity


async def register_user(request: Request, payload: UserRegisterPayload, db: AsyncSession) -> UserRegistrationStartedResponse:
    await _apply_auth_rate_limit(request, scope="auth:register", principal=payload.email)
    password_hash = hash_password(payload.password)
    existing_user = await get_user_by_email(db, payload.email)

    if existing_user is not None and existing_user.is_active and existing_user.is_verified: raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="User with this email already exists")

    try:
        if existing_user is not None:
            if not optional_str(existing_user.username): existing_user.username = str(payload.email)
            existing_user.password_hash = password_hash
            existing_user.name = payload.name
            existing_user.surname = payload.surname
            existing_user.is_active = True
            existing_user.is_verified = False
            user = existing_user
        else: user = await create_user(db, UserCreate(username=str(payload.email), email=payload.email, password_hash=password_hash, name=payload.name, surname=payload.surname, phone_number=None, is_verified=False,), commit=False,)
        await _create_and_send_verification_code(user, db)
        await db.commit()
        await db.refresh(user)
    except IntegrityError as error:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="User with this email already exists") from error
    except (EmailVerificationConfigError, EmailVerificationDeliveryError) as error:
        await db.rollback()
        logger.exception("Failed to send email verification code during registration")
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Could not send verification email") from error

    return UserRegistrationStartedResponse(user_id=user.id, email=user.email, message="Verification code sent")


async def verify_registration_user(request: Request, payload: UserRegisterVerifyPayload, db: AsyncSession) -> AuthTokensWithUserResponse:
    await _apply_auth_rate_limit(request, scope="auth:register_verify", principal=payload.email, verify=True)
    user = await get_user_by_email(db, payload.email)
    if user is None or not user.is_active: raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired verification code")
    if user.is_verified: raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email is already verified")

    await _verify_latest_email_code(user, payload.code, db)
    user.is_verified = True
    await db.commit()
    await db.refresh(user)
    return await _build_auth_tokens_response(user, db)


async def resend_registration_verification_code(request: Request, payload: UserVerificationCodeResendPayload, db: AsyncSession) -> UserVerificationCodeSentResponse:
    await _apply_auth_rate_limit(request, scope="auth:register_resend", principal=payload.email)
    user = await get_user_by_email(db, payload.email)
    if user is None or not user.is_active or user.is_verified: raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found or already verified")

    try:
        await _create_and_send_verification_code(user, db)
        await db.commit()
    except (EmailVerificationConfigError, EmailVerificationDeliveryError) as error:
        await db.rollback()
        logger.exception("Failed to resend email verification code")
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Could not send verification email") from error

    return UserVerificationCodeSentResponse(email=user.email, message="Verification code sent")


async def login_user(request: Request, payload: UserLoginPayload, db: AsyncSession) -> AuthTokensWithUserResponse | AuthVerificationRequiredResponse:
    await _apply_auth_rate_limit(request, scope="auth:login", principal=payload.login)
    user = await _get_login_user(payload, db)

    if _is_app_review_identity(user) and user.is_active and user.is_verified:
        logger.info("App Review customer password login user_id=%s", user.id)
        return await _build_auth_tokens_response(user, db)

    if AUTH_LOGIN_ADMIN_BYPASS_EMAIL_2FA and await is_admin_user(db, user.id): return await _build_auth_tokens_response(user, db)

    try:
        await _create_and_send_verification_code(user, db)
        await db.commit()
    except (EmailVerificationConfigError, EmailVerificationDeliveryError) as error:
        await db.rollback()
        logger.exception("Failed to send email verification code during login")
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Could not send verification email") from error
    return AuthVerificationRequiredResponse(email=user.email, message="Verification code sent")


async def verify_login_user(request: Request, payload: UserLoginVerifyPayload, db: AsyncSession) -> AuthTokensWithUserResponse:
    await _apply_auth_rate_limit(request, scope="auth:login_verify", principal=payload.email, verify=True)
    user = await get_user_by_email(db, payload.email)
    if user is None or not user.is_active: raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired verification code")

    await _verify_latest_email_code(user, payload.code, db)
    if not user.is_verified: user.is_verified = True
    await db.commit()
    await db.refresh(user)
    return await _build_auth_tokens_response(user, db)


async def resend_login_verification_code(request: Request, payload: UserLoginPayload, db: AsyncSession) -> AuthVerificationRequiredResponse:
    await _apply_auth_rate_limit(request, scope="auth:login_resend", principal=payload.login)
    user = await _get_login_user(payload, db)
    try:
        await _create_and_send_verification_code(user, db)
        await db.commit()
    except (EmailVerificationConfigError, EmailVerificationDeliveryError) as error:
        await db.rollback()
        logger.exception("Failed to resend email verification code during login")
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Could not send verification email") from error

    return AuthVerificationRequiredResponse(email=user.email, message="Verification code sent")
