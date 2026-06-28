import secrets

from datetime import timedelta
from logging import getLogger
from fastapi import HTTPException, Request
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status

from config import (
    AUTH_LOGIN_ADMIN_BYPASS_EMAIL_2FA,
    AUTH_LOGIN_WEBSITE_FIRST_ENABLED,
    AUTH_RATE_LIMIT_MAX_REQUESTS,
    AUTH_RATE_LIMIT_WINDOW_SECONDS,
    AUTH_VERIFY_RATE_LIMIT_MAX_REQUESTS,
    EMAIL_VERIFICATION_CODE_TTL_MINUTES,
    EMAIL_VERIFICATION_MAX_ATTEMPTS,
    REFRESH_TOKEN_LIFETIME_DAYS,
    ufa_now,
)
from src.app.modules.auth.schemas.login import UserLoginPayload, UserLoginVerifyPayload
from src.app.modules.auth.schemas.logout import UserLogoutPayload
from src.app.modules.auth.schemas.refresh import UserRefreshPayload
from src.app.modules.auth.schemas.register import (
    UserRegisterPayload,
    UserRegisterVerifyPayload,
    UserVerificationCodeResendPayload,
    UserVerificationCodeSentResponse,
    UserRegistrationStartedResponse,
)
from src.app.modules.auth.schemas.responses import (
    AuthLogoutResponse,
    AuthRefreshResponse,
    AuthTokensWithUserResponse,
    AuthTokensWithWebsiteIdentityResponse,
    AuthUserRead,
    AuthVerificationRequiredResponse,
)
from src.app.modules.auth.schemas.website import WebsiteIdentityLoginPayload
from src.app.services.email_verification import (
    EmailVerificationConfigError,
    EmailVerificationDeliveryError,
    generate_email_verification_code,
    hash_email_verification_code,
    send_user_verification_code_email,
    verify_email_verification_code,
)
from src.app.services.rate_limit import client_ip_from_request, enforce_rate_limit
from src.app.services.security import create_access_token, hash_password, verify_password
from src.app.services.security.refresh import create_refresh_token, hash_refresh_token, verify_refresh_token
from src.app.services.website_identities.service import link_website_identity_to_user, login_with_website_identity
from src.database.crud.auth.admin import is_admin_user
from src.database.crud.auth.email_verification_code import create_email_verification_code, get_latest_pending_email_verification_code
from src.database.crud.auth.user import create_user, get_user_by_email, get_user_by_id, get_user_by_username
from src.database.crud.auth.user_session import (
    create_user_session,
    get_user_session_by_id,
    revoke_active_user_sessions,
    update_user_session,
)
from src.database.models.auth.user import User
from src.database.schemas.auth.user import UserCreate
from src.database.schemas.auth.user_session import UserSessionCreate, UserSessionUpdate
from src.database.schemas.website.website_identity import WebsiteIdentityRead
from src.integrations.website_identity import WebsiteIdentityClient

logger = getLogger(__name__)


def _auth_limit_key(request: Request, principal: str | None = None) -> str:
    ip = client_ip_from_request(request)
    normalized_principal = (principal or "").strip().lower()
    if normalized_principal:
        return f"{ip}:{normalized_principal}"
    return ip


async def _apply_auth_rate_limit(request: Request, *, scope: str, principal: str | None = None, verify: bool = False) -> None:
    await enforce_rate_limit(
        request,
        scope=scope,
        limit=AUTH_VERIFY_RATE_LIMIT_MAX_REQUESTS if verify else AUTH_RATE_LIMIT_MAX_REQUESTS,
        window_seconds=AUTH_RATE_LIMIT_WINDOW_SECONDS,
        key=_auth_limit_key(request, principal),
    )


async def _build_auth_tokens_response(user: User, db: AsyncSession) -> AuthTokensWithUserResponse:
    refresh_token = create_refresh_token()
    refresh_token_hash = hash_refresh_token(refresh_token)

    user_session_create = UserSessionCreate(user_id=user.id, refresh_token_hash=refresh_token_hash)
    session = await create_user_session(db, user_session_create)
    access_token = create_access_token(user_id=user.id, session_id=session.id)

    return AuthTokensWithUserResponse(
        access_token=access_token, refresh_token=refresh_token, session_id=session.id, user=AuthUserRead.model_validate(user)
    )


async def _create_and_send_verification_code(user: User, db: AsyncSession) -> None:
    code = generate_email_verification_code()
    code_hash = hash_email_verification_code(code)
    expires_at = ufa_now() + timedelta(minutes=EMAIL_VERIFICATION_CODE_TTL_MINUTES)
    await create_email_verification_code(db, user_id=user.id, code_hash=code_hash, expires_at=expires_at, commit=False)
    await send_user_verification_code_email(to_email=user.email, code=code)


async def _get_plain_login_user(payload: UserLoginPayload, db: AsyncSession) -> User:
    user = await get_user_by_username(db, payload.login)
    if not user or not user.is_active or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    return user


async def _verify_latest_email_code(user: User, code: str, db: AsyncSession) -> None:
    verification_code = await get_latest_pending_email_verification_code(db, user_id=user.id)
    if verification_code is None or verification_code.attempt_count >= EMAIL_VERIFICATION_MAX_ATTEMPTS:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired verification code")

    if not verify_email_verification_code(code, verification_code.code_hash):
        verification_code.attempt_count += 1
        await db.commit()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid verification code")

    verification_code.used_at = ufa_now()


async def register_user(request: Request, payload: UserRegisterPayload, db: AsyncSession) -> UserRegistrationStartedResponse:
    await _apply_auth_rate_limit(request, scope="auth:register", principal=payload.email)
    password_hash = hash_password(payload.password)
    user_create = UserCreate(
        username=payload.username,
        email=payload.email,
        name=payload.name,
        surname=payload.surname,
        phone_number=payload.phone_number,
        password_hash=password_hash,
    )

    try:
        user = await create_user(db, user_create, commit=False)
        await _create_and_send_verification_code(user, db)
        await db.commit()
        await db.refresh(user)

    except IntegrityError as error:
        await db.rollback()
        existing_user = await get_user_by_email(db, payload.email)
        if existing_user and existing_user.is_active and not existing_user.is_verified and existing_user.username == payload.username:
            try:
                await _create_and_send_verification_code(existing_user, db)
                await db.commit()
            except (EmailVerificationConfigError, EmailVerificationDeliveryError) as resend_error:
                logger.exception("Failed to resend email verification code during duplicate registration")
                raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Could not send verification email") from resend_error

            return UserRegistrationStartedResponse(user_id=existing_user.id, email=existing_user.email, message="Verification code sent")
        logger.exception("Failed to create user during registration")
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="User with this username or email already exists") from error

    except (EmailVerificationConfigError, EmailVerificationDeliveryError) as error:
        logger.exception("Failed to send email verification code during registration")
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Could not send verification email") from error

    return UserRegistrationStartedResponse(user_id=user.id, email=user.email, message="Verification code sent")


async def verify_registration_user(request: Request, payload: UserRegisterVerifyPayload, db: AsyncSession) -> AuthTokensWithUserResponse:
    await _apply_auth_rate_limit(request, scope="auth:register_verify", principal=payload.email, verify=True)
    user = await get_user_by_email(db, payload.email)
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired verification code")

    if user.is_verified:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email is already verified")

    await _verify_latest_email_code(user, payload.code, db)
    user.is_verified = True
    await db.commit()
    await db.refresh(user)

    return await _build_auth_tokens_response(user, db)


async def resend_registration_verification_code(request: Request, payload: UserVerificationCodeResendPayload, db: AsyncSession) -> UserVerificationCodeSentResponse:
    await _apply_auth_rate_limit(request, scope="auth:register_resend", principal=payload.email)
    user = await get_user_by_email(db, payload.email)
    if not user or not user.is_active or user.is_verified:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found or already verified")

    try:
        await _create_and_send_verification_code(user, db)
        await db.commit()
    except (EmailVerificationConfigError, EmailVerificationDeliveryError) as error:
        logger.exception("Failed to resend email verification code")
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Could not send verification email") from error

    return UserVerificationCodeSentResponse(email=user.email, message="Verification code sent")


async def login_user(request: Request, payload: UserLoginPayload, db: AsyncSession, website_identity_client: WebsiteIdentityClient) -> AuthTokensWithUserResponse | AuthVerificationRequiredResponse:
    await _apply_auth_rate_limit(request, scope="auth:login", principal=payload.login)

    website_auth_error: HTTPException | None = None
    if AUTH_LOGIN_WEBSITE_FIRST_ENABLED:
        try:
            website_user, _ = await login_with_website_identity(
                db,
                login=payload.login,
                password=payload.password,
                website_identity_client=website_identity_client,
            )
            return await _build_auth_tokens_response(website_user, db)
        except HTTPException as exc:
            if exc.status_code == status.HTTP_401_UNAUTHORIZED:
                pass
            else:
                website_auth_error = exc

    try:
        user = await _get_plain_login_user(payload, db)
    except HTTPException as exc:
        if website_auth_error is not None:
            raise website_auth_error from exc
        raise

    if AUTH_LOGIN_ADMIN_BYPASS_EMAIL_2FA and await is_admin_user(db, user.id):
        return await _build_auth_tokens_response(user, db)
    try:
        await _create_and_send_verification_code(user, db)
        await db.commit()
    except (EmailVerificationConfigError, EmailVerificationDeliveryError) as error:
        logger.exception("Failed to send email verification code during login")
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Could not send verification email") from error
    return AuthVerificationRequiredResponse(email=user.email, message="Verification code sent")


async def verify_login_user(request: Request, payload: UserLoginVerifyPayload, db: AsyncSession) -> AuthTokensWithUserResponse:
    await _apply_auth_rate_limit(request, scope="auth:login_verify", principal=payload.email, verify=True)
    user = await get_user_by_email(db, payload.email)
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired verification code")

    await _verify_latest_email_code(user, payload.code, db)
    if not user.is_verified:
        user.is_verified = True
    await db.commit()
    await db.refresh(user)
    return await _build_auth_tokens_response(user, db)


async def resend_login_verification_code(request: Request, payload: UserLoginPayload, db: AsyncSession) -> AuthVerificationRequiredResponse:
    await _apply_auth_rate_limit(request, scope="auth:login_resend", principal=payload.login)
    user = await _get_plain_login_user(payload, db)
    try:
        await _create_and_send_verification_code(user, db)
        await db.commit()
    except (EmailVerificationConfigError, EmailVerificationDeliveryError) as error:
        logger.exception("Failed to resend email verification code during login")
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Could not send verification email") from error

    return AuthVerificationRequiredResponse(email=user.email, message="Verification code sent")


async def login_user_with_website(request: Request, payload: WebsiteIdentityLoginPayload, db: AsyncSession, website_identity_client: WebsiteIdentityClient) -> AuthTokensWithWebsiteIdentityResponse:
    await _apply_auth_rate_limit(request, scope="auth:website_login", principal=payload.login)
    user, website_identity = await login_with_website_identity(
        db,
        login=payload.login,
        password=payload.password,
        website_identity_client=website_identity_client,
    )
    auth_response = await _build_auth_tokens_response(user, db)

    return AuthTokensWithWebsiteIdentityResponse(
        access_token=auth_response.access_token,
        refresh_token=auth_response.refresh_token,
        session_id=auth_response.session_id,
        user=auth_response.user,
        website_identity=WebsiteIdentityRead.model_validate(website_identity),
    )


async def parse_website_identity_for_user(request: Request, payload: WebsiteIdentityLoginPayload, current_user: User, db: AsyncSession, website_identity_client: WebsiteIdentityClient) -> WebsiteIdentityRead:
    await _apply_auth_rate_limit(request, scope="auth:website_parse", principal=payload.login)
    website_identity = await link_website_identity_to_user(
        db,
        user=current_user,
        login=payload.login,
        password=payload.password,
        website_identity_client=website_identity_client,
    )
    return WebsiteIdentityRead.model_validate(website_identity)


async def refresh_user_tokens(request: Request, payload: UserRefreshPayload, db: AsyncSession) -> AuthRefreshResponse:
    await _apply_auth_rate_limit(request, scope="auth:refresh", principal=str(payload.session_id), verify=True)
    session = await get_user_session_by_id(db, payload.session_id)
    if not session:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Could not validate credentials")

    if session.revoked_at is not None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session has been revoked")

    if session.expires_at <= ufa_now():
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token has expired")

    if not verify_refresh_token(payload.refresh_token, session.refresh_token_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Could not validate credentials")

    user = await get_user_by_id(db, session.user_id)
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Could not validate credentials")

    new_refresh_token = create_refresh_token()
    new_refresh_token_hash = hash_refresh_token(new_refresh_token)

    user_session_update = UserSessionUpdate(
        refresh_token_hash=new_refresh_token_hash,
        last_used_at=ufa_now(),
        expires_at=ufa_now() + timedelta(days=REFRESH_TOKEN_LIFETIME_DAYS),
    )

    await update_user_session(db, session, user_session_update)
    access_token = create_access_token(user_id=user.id, session_id=session.id)

    return AuthRefreshResponse(access_token=access_token, refresh_token=new_refresh_token, session_id=session.id)


async def logout_user_session(request: Request, payload: UserLogoutPayload, db: AsyncSession) -> AuthLogoutResponse:
    await _apply_auth_rate_limit(request, scope="auth:logout", principal=str(payload.session_id), verify=True)
    session = await get_user_session_by_id(db, payload.session_id)
    if not session:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Could not validate credentials")

    if not verify_refresh_token(payload.refresh_token, session.refresh_token_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Could not validate credentials")

    if session.revoked_at is None:
        user_session_update = UserSessionUpdate(revoked_at=ufa_now())
        await update_user_session(db, session, user_session_update)

    return AuthLogoutResponse(ok=True, message="Logged out successfully")


async def delete_user_account(request: Request, current_user: User, db: AsyncSession) -> AuthLogoutResponse:
    await _apply_auth_rate_limit(request, scope="auth:delete_account", principal=str(current_user.id), verify=True)

    now = ufa_now()
    suffix = f"{current_user.id}_{int(now.timestamp())}"
    current_user.username = f"del_{str(current_user.id)[-12:]}"
    current_user.email = f"deleted_{suffix}@example.invalid"
    current_user.name = "Deleted"
    current_user.surname = "User"
    current_user.phone_number = None
    current_user.contact_id = None
    current_user.is_verified = False
    current_user.is_active = False
    current_user.password_hash = hash_password(secrets.token_urlsafe(32))
    current_user.last_active_at = now

    await revoke_active_user_sessions(
        db,
        user_id=current_user.id,
        revoked_at=now,
        commit=False,
    )
    await db.commit()

    return AuthLogoutResponse(ok=True, message="Account deleted")
