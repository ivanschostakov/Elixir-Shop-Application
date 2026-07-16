import hashlib
import hmac
import json
import secrets
import time

from datetime import timedelta
from logging import getLogger
from urllib.parse import parse_qsl

from fastapi import HTTPException, Request
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status

from config import (
    AUTH_LOGIN_ADMIN_BYPASS_EMAIL_2FA,
    AUTH_RATE_LIMIT_MAX_REQUESTS,
    AUTH_RATE_LIMIT_WINDOW_SECONDS,
    AUTH_VERIFY_RATE_LIMIT_MAX_REQUESTS,
    EMAIL_VERIFICATION_CODE_TTL_MINUTES,
    EMAIL_VERIFICATION_MAX_ATTEMPTS,
    REFRESH_TOKEN_LIFETIME_DAYS,
    TELEGRAM_AUTH_MAX_AGE_SECONDS,
    TELEGRAM_BOT_TOKEN,
    ufa_now,
)
from src.app.modules.auth.schemas.login import UserLoginPayload, UserLoginVerifyPayload
from src.app.modules.auth.schemas.phone import (
    PhoneAuthClaimPayload,
    PhoneAuthCodeResendPayload,
    PhoneAuthCodeSentResponse,
    PhoneAuthLoginPayload,
    PhoneAuthRegisterPayload,
    PhoneAuthStartPayload,
    PhoneAuthStartResponse,
    PhoneAuthVerificationRequiredResponse,
    PhoneAuthVerifyPayload,
)
from src.app.modules.auth.schemas.register import (
    UserRegisterPayload,
    UserRegisterVerifyPayload,
    UserRegistrationStartedResponse,
    UserVerificationCodeResendPayload,
    UserVerificationCodeSentResponse,
)
from src.app.modules.auth.schemas.logout import UserLogoutPayload
from src.app.modules.auth.schemas.refresh import UserRefreshPayload
from src.app.modules.auth.schemas.responses import (
    AuthLogoutResponse,
    AuthRefreshResponse,
    AuthTokensWithUserResponse,
    AuthUserRead,
    AuthVerificationRequiredResponse,
)
from src.app.modules.auth.schemas.telegram import (
    TelegramAuthContactRequiredResponse,
    TelegramAuthPayload,
)
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
from src.database.crud.auth.admin import is_admin_user
from src.database.crud.auth.email_verification_code import (
    create_email_verification_code,
    get_latest_pending_email_verification_code,
)
from src.database.crud.auth.user import (
    create_user,
    get_user_by_email,
    get_user_by_id,
    get_user_by_phone_number,
    get_user_by_telegram_user_id,
)
from src.database.crud.auth.user_session import (
    create_user_session,
    get_user_session_by_id,
    revoke_active_user_sessions,
    update_user_session,
)
from src.database.limits import PERSON_NAME_MAX_LENGTH, PHONE_NUMBER_MAX_LENGTH, TELEGRAM_USERNAME_MAX_LENGTH
from src.database.models.auth.user import User
from src.database.schemas.auth.user import UserCreate
from src.database.schemas.auth.user_session import UserSessionCreate, UserSessionUpdate
from src.integrations.moysklad import MoySkladClient, get_moysklad_client
from src.normalize import coerce_uuid, normalize_email, normalize_phone, optional_str

logger = getLogger(__name__)


def _auth_limit_key(request: Request, principal: str | None = None) -> str:
    ip = client_ip_from_request(request)
    normalized_principal = (principal or "").strip().lower()
    return f"{ip}:{normalized_principal}" if normalized_principal else ip


def _mask_email(email: str | None) -> str | None:
    normalized = normalize_email(email)
    if not normalized:
        return None
    local, _, domain = normalized.partition("@")
    if not local or not domain:
        return None
    masked_local = local[:2] + "*" * max(len(local) - 2, 1)
    return f"{masked_local}@{domain}"


def _counterparty_email(counterparty: dict[str, object] | None) -> str | None:
    if not isinstance(counterparty, dict):
        return None
    return normalize_email(counterparty.get("email"))


def _counterparty_name_parts(counterparty: dict[str, object] | None) -> tuple[str, str]:
    raw_name = optional_str(counterparty.get("name") if isinstance(counterparty, dict) else None) or "Customer"
    parts = raw_name.split()
    if len(parts) == 1:
        return raw_name[:PERSON_NAME_MAX_LENGTH], "Customer"
    return parts[0][:PERSON_NAME_MAX_LENGTH], " ".join(parts[1:])[:PERSON_NAME_MAX_LENGTH] or "Customer"


def _deleted_phone_number(*, user_id: int, timestamp: int) -> str:
    suffix = f"{user_id % 100000:05d}{timestamp % 100000000:08d}"
    return f"+98{suffix}"


def _telegram_config_unavailable() -> HTTPException:
    return HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Telegram auth is not configured")


def _fit_person_name(value: object, fallback: str) -> str:
    normalized = optional_str(value) or fallback
    return normalized[:PERSON_NAME_MAX_LENGTH] or fallback


def _fit_telegram_username(value: object) -> str | None:
    normalized = optional_str(value)
    return normalized[:TELEGRAM_USERNAME_MAX_LENGTH] if normalized else None


def _normalize_telegram_phone(value: object) -> str | None:
    normalized = normalize_phone(value)
    if normalized is None:
        return None
    if not normalized.startswith("+"):
        normalized = f"+{normalized}"
    return normalized[:PHONE_NUMBER_MAX_LENGTH]


def _validate_telegram_init_data(init_data: str) -> dict[str, object]:
    if not TELEGRAM_BOT_TOKEN:
        raise _telegram_config_unavailable()

    pairs = parse_qsl(init_data, keep_blank_values=True, strict_parsing=False)
    values = dict(pairs)
    received_hash = values.pop("hash", "")
    if not received_hash:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid Telegram auth data")

    data_check_string = "\n".join(f"{key}={value}" for key, value in sorted(values.items()))
    secret_key = hmac.new(b"WebAppData", TELEGRAM_BOT_TOKEN.encode("utf-8"), hashlib.sha256).digest()
    expected_hash = hmac.new(secret_key, data_check_string.encode("utf-8"), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected_hash, received_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid Telegram auth data")

    try:
        auth_date = int(values.get("auth_date", "0"))
    except (TypeError, ValueError):
        auth_date = 0
    if auth_date <= 0 or time.time() - auth_date > TELEGRAM_AUTH_MAX_AGE_SECONDS:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Expired Telegram auth data")

    try:
        user = json.loads(values.get("user", "{}"))
    except (TypeError, json.JSONDecodeError) as error:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid Telegram auth user") from error

    if not isinstance(user, dict):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid Telegram auth user")
    try:
        telegram_user_id = int(user["id"])
    except (KeyError, TypeError, ValueError) as error:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid Telegram auth user") from error
    if telegram_user_id <= 0:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid Telegram auth user")

    return {
        "id": telegram_user_id,
        "first_name": user.get("first_name"),
        "last_name": user.get("last_name"),
        "username": user.get("username"),
        "auth_date": auth_date,
    }


def _apply_telegram_profile(user: User, telegram_user: dict[str, object]) -> bool:
    changed = False
    telegram_user_id = int(telegram_user["id"])
    telegram_username = _fit_telegram_username(telegram_user.get("username"))

    if user.telegram_user_id != telegram_user_id:
        user.telegram_user_id = telegram_user_id
        changed = True
    if user.telegram_username != telegram_username:
        user.telegram_username = telegram_username
        changed = True

    return changed


def _is_telegram_user_phone_confirmed(user: User, telegram_user_id: int) -> bool:
    return (
        user.is_active
        and user.telegram_user_id == telegram_user_id
        and user.telegram_phone_confirmed_at is not None
        and bool(user.phone_number)
    )


def verify_telegram_init_data_for_user(init_data: str, user: User) -> tuple[bool, str | None]:
    try:
        telegram_user = _validate_telegram_init_data(init_data)
    except HTTPException as error:
        return False, str(error.detail)

    telegram_user_id = int(telegram_user["id"])
    if not _is_telegram_user_phone_confirmed(user, telegram_user_id):
        return False, "telegram user is not linked to the current user"

    return True, None


async def _apply_auth_rate_limit(request: Request, *, scope: str, principal: str | None = None, verify: bool = False) -> None:
    await enforce_rate_limit(
        request,
        scope=scope,
        limit=AUTH_VERIFY_RATE_LIMIT_MAX_REQUESTS if verify else AUTH_RATE_LIMIT_MAX_REQUESTS,
        window_seconds=AUTH_RATE_LIMIT_WINDOW_SECONDS,
        key=_auth_limit_key(request, principal),
    )


async def _get_counterparty_for_phone(phone_number: str, moysklad_client: MoySkladClient) -> dict[str, object] | None:
    if not moysklad_client.is_configured():
        return None
    row = await moysklad_client.get_counterparty_by_phone(phone_number)
    return row if isinstance(row, dict) else None


async def _resolve_user_for_phone(
    db: AsyncSession,
    phone_number: str,
    moysklad_client: MoySkladClient,
) -> tuple[User | None, dict[str, object] | None]:
    user = await get_user_by_phone_number(db, phone_number)
    counterparty = await _get_counterparty_for_phone(phone_number, moysklad_client)
    if user is not None and user.is_active:
        return user, counterparty
    return None, counterparty


async def _link_moysklad_counterparty_by_email(user: User, db: AsyncSession) -> None:
    if user.moysklad_counterparty_id is not None:
        return

    email = normalize_email(user.email)
    if not email:
        return

    moysklad_client = get_moysklad_client()
    if not moysklad_client.is_configured():
        return

    try:
        counterparty = await moysklad_client.get_counterparty_by_email(email)
    except Exception:
        logger.exception(
            "Failed to find MoySklad counterparty by email during authentication user_id=%s",
            user.id,
        )
        return

    counterparty_id = coerce_uuid(counterparty.get("id")) if isinstance(counterparty, dict) else None
    if counterparty_id is None:
        return

    try:
        user.moysklad_counterparty_id = counterparty_id
        await db.commit()
        await db.refresh(user)
    except Exception:
        await db.rollback()
        await db.refresh(user)
        logger.exception(
            "Failed to save MoySklad counterparty email link during authentication user_id=%s",
            user.id,
        )


def _sync_phone_identity_from_counterparty(user: User, *, phone_number: str, counterparty: dict[str, object] | None) -> bool:
    changed = False
    if normalize_phone(user.phone_number) != phone_number:
        user.phone_number = phone_number
        changed = True

    counterparty_id = coerce_uuid(counterparty.get("id")) if isinstance(counterparty, dict) else None
    if counterparty_id is not None and user.moysklad_counterparty_id != counterparty_id:
        user.moysklad_counterparty_id = counterparty_id
        changed = True

    return changed


async def _build_auth_tokens_response(user: User, db: AsyncSession) -> AuthTokensWithUserResponse:
    await _link_moysklad_counterparty_by_email(user, db)
    refresh_token = create_refresh_token()
    refresh_token_hash = hash_refresh_token(refresh_token)
    session = await create_user_session(db, UserSessionCreate(user_id=user.id, refresh_token_hash=refresh_token_hash))
    access_token = create_access_token(user_id=user.id, session_id=session.id)
    return AuthTokensWithUserResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        session_id=session.id,
        user=AuthUserRead.model_validate(user),
    )


async def _create_and_send_verification_code(user: User, db: AsyncSession) -> None:
    if not user.email:
        raise RuntimeError("Cannot create an email verification code for a user without email")
    code = generate_email_verification_code()
    code_hash = hash_email_verification_code(code)
    expires_at = ufa_now() + timedelta(minutes=EMAIL_VERIFICATION_CODE_TTL_MINUTES)
    await create_email_verification_code(db, user_id=user.id, code_hash=code_hash, expires_at=expires_at, commit=False)
    await send_user_verification_code_email(to_email=user.email, code=code)


async def _verify_latest_email_code(user: User, code: str, db: AsyncSession) -> None:
    verification_code = await get_latest_pending_email_verification_code(db, user_id=user.id)
    if verification_code is None or verification_code.attempt_count >= EMAIL_VERIFICATION_MAX_ATTEMPTS:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired verification code")

    if not verify_email_verification_code(code, verification_code.code_hash):
        verification_code.attempt_count += 1
        await db.commit()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid verification code")

    verification_code.used_at = ufa_now()


async def _get_email_login_user(payload: UserLoginPayload, db: AsyncSession) -> User:
    user = await get_user_by_email(db, payload.login)
    if user is None or not user.is_active or not user.email or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    return user


async def register_user(request: Request, payload: UserRegisterPayload, db: AsyncSession) -> UserRegistrationStartedResponse:
    await _apply_auth_rate_limit(request, scope="auth:register", principal=payload.email)
    password_hash = hash_password(payload.password)
    existing_user = await get_user_by_email(db, payload.email)

    if existing_user is not None and existing_user.is_active and existing_user.is_verified:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="User with this email already exists")

    try:
        if existing_user is not None:
            existing_user.password_hash = password_hash
            existing_user.name = payload.name
            existing_user.surname = payload.surname
            existing_user.is_active = True
            existing_user.is_verified = False
            user = existing_user
        else:
            user = await create_user(
                db,
                UserCreate(
                    email=payload.email,
                    password_hash=password_hash,
                    name=payload.name,
                    surname=payload.surname,
                    phone_number=None,
                    is_verified=False,
                ),
                commit=False,
            )
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
    if user is None or not user.is_active:
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
    if user is None or not user.is_active or user.is_verified:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found or already verified")

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
    user = await _get_email_login_user(payload, db)

    if AUTH_LOGIN_ADMIN_BYPASS_EMAIL_2FA and await is_admin_user(db, user.id):
        return await _build_auth_tokens_response(user, db)

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
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired verification code")

    await _verify_latest_email_code(user, payload.code, db)
    if not user.is_verified:
        user.is_verified = True
    await db.commit()
    await db.refresh(user)
    return await _build_auth_tokens_response(user, db)


async def resend_login_verification_code(request: Request, payload: UserLoginPayload, db: AsyncSession) -> AuthVerificationRequiredResponse:
    await _apply_auth_rate_limit(request, scope="auth:login_resend", principal=payload.login)
    user = await _get_email_login_user(payload, db)
    try:
        await _create_and_send_verification_code(user, db)
        await db.commit()
    except (EmailVerificationConfigError, EmailVerificationDeliveryError) as error:
        await db.rollback()
        logger.exception("Failed to resend email verification code during login")
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Could not send verification email") from error

    return AuthVerificationRequiredResponse(email=user.email, message="Verification code sent")


async def _finalize_phone_auth_setup(user: User, db: AsyncSession) -> AuthTokensWithUserResponse | PhoneAuthVerificationRequiredResponse:
    if user.email:
        try:
            await _create_and_send_verification_code(user, db)
            await db.commit()
            await db.refresh(user)
        except (EmailVerificationConfigError, EmailVerificationDeliveryError) as error:
            await db.rollback()
            logger.exception("Failed to send email verification code during phone auth setup")
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Could not send verification email") from error

        return PhoneAuthVerificationRequiredResponse(
            phone_number=user.phone_number,
            email=user.email,
            message="Verification code sent",
        )

    user.is_verified = True
    await db.commit()
    await db.refresh(user)
    return await _build_auth_tokens_response(user, db)


async def start_phone_auth(request: Request, payload: PhoneAuthStartPayload, db: AsyncSession, moysklad_client: MoySkladClient) -> PhoneAuthStartResponse:
    await _apply_auth_rate_limit(request, scope="auth:phone_start", principal=payload.phone_number)
    user, counterparty = await _resolve_user_for_phone(db, payload.phone_number, moysklad_client)

    if user is not None:
        if user.is_verified:
            return PhoneAuthStartResponse(
                phone_number=payload.phone_number,
                next_step="login",
                message="Enter your password",
            )

        next_step = "claim" if counterparty is not None or user.moysklad_counterparty_id is not None else "register"
        email = user.email or _counterparty_email(counterparty)
        return PhoneAuthStartResponse(
            phone_number=payload.phone_number,
            next_step=next_step,
            email_required=next_step == "claim" and not bool(email),
            email_hint=_mask_email(email),
            message="Continue account setup",
        )

    if counterparty is not None:
        email = _counterparty_email(counterparty)
        return PhoneAuthStartResponse(
            phone_number=payload.phone_number,
            next_step="claim",
            email_required=not bool(email),
            email_hint=_mask_email(email),
            message="We found your customer profile",
        )

    return PhoneAuthStartResponse(
        phone_number=payload.phone_number,
        next_step="register",
        email_required=False,
        message="Create a new account",
    )


async def login_user_by_phone(request: Request, payload: PhoneAuthLoginPayload, db: AsyncSession, moysklad_client: MoySkladClient) -> AuthTokensWithUserResponse:
    await _apply_auth_rate_limit(request, scope="auth:phone_login", principal=payload.phone_number)
    user, counterparty = await _resolve_user_for_phone(db, payload.phone_number, moysklad_client)
    if user is None or not user.is_active or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    changed = _sync_phone_identity_from_counterparty(user, phone_number=payload.phone_number, counterparty=counterparty)
    if changed:
        await db.commit()
        await db.refresh(user)

    return await _build_auth_tokens_response(user, db)


async def claim_user_by_phone(
    request: Request,
    payload: PhoneAuthClaimPayload,
    db: AsyncSession,
    moysklad_client: MoySkladClient,
) -> AuthTokensWithUserResponse | PhoneAuthVerificationRequiredResponse:
    await _apply_auth_rate_limit(request, scope="auth:phone_claim", principal=payload.phone_number)
    counterparty = await _get_counterparty_for_phone(payload.phone_number, moysklad_client)
    if counterparty is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Counterparty was not found for this phone number")

    existing_phone_user = await get_user_by_phone_number(db, payload.phone_number)
    if existing_phone_user is not None and existing_phone_user.is_active and existing_phone_user.is_verified:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Account already exists for this phone number")

    email = payload.email or _counterparty_email(counterparty) or (normalize_email(existing_phone_user.email) if existing_phone_user is not None else None)
    existing_email_user = await get_user_by_email(db, email)
    if (
        email
        and existing_email_user is not None
        and existing_email_user.is_active
        and (existing_phone_user is None or existing_email_user.id != existing_phone_user.id)
    ):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="User with this email already exists")

    password_hash = hash_password(payload.password)
    name, surname = _counterparty_name_parts(counterparty)
    counterparty_id = coerce_uuid(counterparty.get("id"))

    try:
        if existing_phone_user is not None and existing_phone_user.is_active:
            existing_phone_user.email = email
            existing_phone_user.password_hash = password_hash
            existing_phone_user.name = name
            existing_phone_user.surname = surname
            existing_phone_user.phone_number = payload.phone_number
            existing_phone_user.moysklad_counterparty_id = counterparty_id
            existing_phone_user.is_verified = not bool(email)
            target_user = existing_phone_user
        else:
            target_user = await create_user(
                db,
                UserCreate(
                    email=email,
                    password_hash=password_hash,
                    name=name,
                    surname=surname,
                    phone_number=payload.phone_number,
                    is_verified=not bool(email),
                    moysklad_counterparty_id=counterparty_id,
                ),
                commit=False,
            )
        return await _finalize_phone_auth_setup(target_user, db)
    except IntegrityError as error:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="User with this phone number or email already exists") from error


async def register_user_by_phone(
    request: Request,
    payload: PhoneAuthRegisterPayload,
    db: AsyncSession,
    moysklad_client: MoySkladClient,
) -> AuthTokensWithUserResponse | PhoneAuthVerificationRequiredResponse:
    await _apply_auth_rate_limit(request, scope="auth:phone_register", principal=payload.phone_number)
    existing_phone_user = await get_user_by_phone_number(db, payload.phone_number)
    if existing_phone_user is not None and existing_phone_user.is_active and existing_phone_user.is_verified:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Account already exists for this phone number")

    counterparty = await _get_counterparty_for_phone(payload.phone_number, moysklad_client)
    if counterparty is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Counterparty already exists for this phone number")

    email = payload.email or (normalize_email(existing_phone_user.email) if existing_phone_user is not None else None)
    existing_email_user = await get_user_by_email(db, email)
    if (
        email
        and existing_email_user is not None
        and existing_email_user.is_active
        and (existing_phone_user is None or existing_email_user.id != existing_phone_user.id)
    ):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="User with this email already exists")

    password_hash = hash_password(payload.password)

    try:
        if existing_phone_user is not None and existing_phone_user.is_active:
            existing_phone_user.email = email
            existing_phone_user.password_hash = password_hash
            existing_phone_user.name = payload.name
            existing_phone_user.surname = payload.surname
            existing_phone_user.phone_number = payload.phone_number
            existing_phone_user.moysklad_counterparty_id = None
            existing_phone_user.is_verified = not bool(email)
            target_user = existing_phone_user
        else:
            target_user = await create_user(
                db,
                UserCreate(
                    email=email,
                    password_hash=password_hash,
                    name=payload.name,
                    surname=payload.surname,
                    phone_number=payload.phone_number,
                    is_verified=not bool(email),
                ),
                commit=False,
            )
        return await _finalize_phone_auth_setup(target_user, db)
    except IntegrityError as error:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="User with this phone number or email already exists") from error


async def verify_phone_auth(request: Request, payload: PhoneAuthVerifyPayload, db: AsyncSession, moysklad_client: MoySkladClient) -> AuthTokensWithUserResponse:
    await _apply_auth_rate_limit(request, scope="auth:phone_verify", principal=payload.phone_number, verify=True)
    user = await get_user_by_phone_number(db, payload.phone_number)
    if user is None or not user.is_active or not user.email:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired verification code")

    if user.is_verified:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email is already verified")

    await _verify_latest_email_code(user, payload.code, db)
    user.is_verified = True
    await db.commit()
    await db.refresh(user)

    if user.moysklad_counterparty_id is not None:
        try:
            await moysklad_client.update_counterparty_email(user.moysklad_counterparty_id, user.email)
        except Exception:
            logger.exception("Failed to sync verified email back to MoySklad counterparty user_id=%s", user.id)

    return await _build_auth_tokens_response(user, db)


async def resend_phone_auth_verification_code(request: Request, payload: PhoneAuthCodeResendPayload, db: AsyncSession) -> PhoneAuthCodeSentResponse:
    await _apply_auth_rate_limit(request, scope="auth:phone_resend", principal=payload.phone_number)
    user = await get_user_by_phone_number(db, payload.phone_number)
    if user is None or not user.is_active or user.is_verified:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found or already verified")
    if not user.email:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email verification is unavailable for this account")

    try:
        await _create_and_send_verification_code(user, db)
        await db.commit()
    except (EmailVerificationConfigError, EmailVerificationDeliveryError) as error:
        logger.exception("Failed to resend phone auth verification code")
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Could not send verification email") from error

    return PhoneAuthCodeSentResponse(phone_number=payload.phone_number, email=user.email, message="Verification code sent")


async def login_user_by_telegram(
    request: Request,
    payload: TelegramAuthPayload,
    db: AsyncSession,
) -> AuthTokensWithUserResponse | TelegramAuthContactRequiredResponse:
    await _apply_auth_rate_limit(request, scope="auth:telegram")
    telegram_user = _validate_telegram_init_data(payload.init_data)
    telegram_user_id = int(telegram_user["id"])
    user = await get_user_by_telegram_user_id(db, telegram_user_id)

    if user is not None and _is_telegram_user_phone_confirmed(user, telegram_user_id):
        changed = _apply_telegram_profile(user, telegram_user)
        if changed:
            user.last_active_at = ufa_now()
            await db.commit()
            await db.refresh(user)
        return await _build_auth_tokens_response(user, db)

    return TelegramAuthContactRequiredResponse(telegram_user_id=telegram_user_id)


async def link_telegram_contact_to_user(
    db: AsyncSession,
    *,
    telegram_user_id: int,
    phone_number: str,
    first_name: object = None,
    last_name: object = None,
    username: object = None,
    moysklad_client: MoySkladClient | None = None,
) -> tuple[User | None, str | None]:
    normalized_phone = _normalize_telegram_phone(phone_number)
    if telegram_user_id <= 0:
        return None, "invalid_telegram_user"
    if not normalized_phone:
        return None, "invalid_phone"

    telegram_user = {
        "id": telegram_user_id,
        "first_name": first_name,
        "last_name": last_name,
        "username": username,
    }
    now = ufa_now()
    user_by_telegram = await get_user_by_telegram_user_id(db, telegram_user_id)
    user_by_phone = await get_user_by_phone_number(db, normalized_phone)
    counterparty: dict[str, object] | None = None
    if moysklad_client is not None:
        try:
            counterparty = await _get_counterparty_for_phone(normalized_phone, moysklad_client)
        except Exception:
            logger.exception("Failed to resolve MoySklad counterparty for Telegram phone")
            counterparty = None
    counterparty_id = coerce_uuid(counterparty.get("id")) if isinstance(counterparty, dict) else None

    if (
        user_by_phone is not None
        and user_by_phone.telegram_user_id is not None
        and user_by_phone.telegram_user_id != telegram_user_id
    ):
        return None, "phone_already_linked_to_another_telegram_user"

    if user_by_telegram is not None and user_by_phone is not None and user_by_telegram.id != user_by_phone.id:
        return None, "telegram_user_and_phone_belong_to_different_users"

    target_user = user_by_telegram or user_by_phone

    try:
        if target_user is None:
            target_user = await create_user(
                db,
                UserCreate(
                    email=None,
                    password_hash=hash_password(secrets.token_urlsafe(32)),
                    name=_fit_person_name(first_name, "Telegram"),
                    surname=_fit_person_name(last_name, "User"),
                    phone_number=normalized_phone,
                    is_verified=True,
                    moysklad_counterparty_id=counterparty_id,
                    telegram_user_id=telegram_user_id,
                    telegram_username=_fit_telegram_username(username),
                    telegram_phone_confirmed_at=now,
                ),
                commit=False,
            )
        else:
            _sync_phone_identity_from_counterparty(target_user, phone_number=normalized_phone, counterparty=counterparty)
            target_user.telegram_phone_confirmed_at = now
            target_user.last_active_at = now
            target_user.is_active = True
            target_user.is_verified = True
            _apply_telegram_profile(target_user, telegram_user)

        await db.commit()
        await db.refresh(target_user)
        return target_user, None
    except IntegrityError:
        await db.rollback()
        return None, "telegram_contact_conflict"


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
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Could not validate credentials")

    new_refresh_token = create_refresh_token()
    await update_user_session(
        db,
        session,
        UserSessionUpdate(
            refresh_token_hash=hash_refresh_token(new_refresh_token),
            last_used_at=ufa_now(),
            expires_at=ufa_now() + timedelta(days=REFRESH_TOKEN_LIFETIME_DAYS),
        ),
    )
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
        await update_user_session(db, session, UserSessionUpdate(revoked_at=ufa_now()))
    return AuthLogoutResponse(ok=True, message="Logged out successfully")


async def delete_user_account(request: Request, current_user: User, db: AsyncSession) -> AuthLogoutResponse:
    await _apply_auth_rate_limit(request, scope="auth:delete_account", principal=str(current_user.id), verify=True)

    now = ufa_now()
    current_user.email = None
    current_user.name = "Deleted"
    current_user.surname = "User"
    current_user.phone_number = _deleted_phone_number(user_id=current_user.id, timestamp=int(now.timestamp()))
    current_user.contact_id = None
    current_user.moysklad_counterparty_id = None
    current_user.is_verified = False
    current_user.is_active = False
    current_user.password_hash = hash_password(secrets.token_urlsafe(32))
    current_user.last_active_at = now

    await revoke_active_user_sessions(db, user_id=current_user.id, revoked_at=now, commit=False)
    await db.commit()
    return AuthLogoutResponse(ok=True, message="Account deleted")
