from fastapi import HTTPException, Request
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status
from src.app.modules.auth.schemas.phone import PhoneAuthClaimPayload, PhoneAuthCodeResendPayload, PhoneAuthCodeSentResponse, PhoneAuthLoginPayload, PhoneAuthRegisterPayload, PhoneAuthStartPayload, PhoneAuthStartResponse, PhoneAuthVerificationRequiredResponse, PhoneAuthVerifyPayload
from src.app.modules.auth.schemas.responses import AuthTokensWithUserResponse
from src.app.services.email_verification import EmailVerificationConfigError, EmailVerificationDeliveryError
from src.app.services.security import hash_password, verify_password
from src.database.crud.auth.user import create_user, get_user_by_email, get_user_by_phone_number
from src.database.models.auth.user import User
from src.database.schemas.auth.user import UserCreate
from src.integrations.moysklad import MoySkladClient
from src.normalize import coerce_uuid, normalize_email, optional_str
from .common import logger
from .utils import _counterparty_email, _counterparty_name_parts, _mask_email
from .rate_limits import _apply_auth_rate_limit
from .counterparty import _get_counterparty_for_phone, _resolve_user_for_phone, _sync_phone_identity_from_counterparty
from .sessions import _build_auth_tokens_response
from .verification import _create_and_send_verification_code, _verify_latest_email_code


async def _finalize_phone_auth_setup(user: User, db: AsyncSession) -> AuthTokensWithUserResponse | PhoneAuthVerificationRequiredResponse:
    if user.email:
        if not optional_str(user.username): user.username = user.email
        try:
            await _create_and_send_verification_code(user, db)
            await db.commit()
            await db.refresh(user)
        except (EmailVerificationConfigError, EmailVerificationDeliveryError) as error:
            await db.rollback()
            logger.exception("Failed to send email verification code during phone auth setup")
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Could not send verification email") from error

        return PhoneAuthVerificationRequiredResponse(phone_number=user.phone_number, email=user.email, message="Verification code sent",)

    user.is_verified = True
    await db.commit()
    await db.refresh(user)
    return await _build_auth_tokens_response(user, db)


async def start_phone_auth(request: Request, payload: PhoneAuthStartPayload, db: AsyncSession, moysklad_client: MoySkladClient) -> PhoneAuthStartResponse:
    await _apply_auth_rate_limit(request, scope="auth:phone_start", principal=payload.phone_number)
    user, counterparty = await _resolve_user_for_phone(db, payload.phone_number, moysklad_client)

    if user is not None:
        if user.is_verified: return PhoneAuthStartResponse(phone_number=payload.phone_number, next_step="login", message="Enter your password",)

        next_step = "claim" if counterparty is not None or user.moysklad_counterparty_id is not None else "register"
        email = user.email or _counterparty_email(counterparty)
        return PhoneAuthStartResponse(phone_number=payload.phone_number, next_step=next_step, email_required=next_step == "claim" and not bool(email), email_hint=_mask_email(email), message="Continue account setup",)

    if counterparty is not None:
        email = _counterparty_email(counterparty)
        return PhoneAuthStartResponse(phone_number=payload.phone_number, next_step="claim", email_required=not bool(email), email_hint=_mask_email(email), message="We found your customer profile",)

    return PhoneAuthStartResponse(phone_number=payload.phone_number, next_step="register", email_required=False, message="Create a new account",)


async def login_user_by_phone(request: Request, payload: PhoneAuthLoginPayload, db: AsyncSession, moysklad_client: MoySkladClient) -> AuthTokensWithUserResponse:
    await _apply_auth_rate_limit(request, scope="auth:phone_login", principal=payload.phone_number)
    user, counterparty = await _resolve_user_for_phone(db, payload.phone_number, moysklad_client)
    if user is None or not user.is_active or not verify_password(payload.password, user.password_hash): raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    changed = _sync_phone_identity_from_counterparty(user, phone_number=payload.phone_number, counterparty=counterparty)
    if changed:
        await db.commit()
        await db.refresh(user)

    return await _build_auth_tokens_response(user, db)


async def claim_user_by_phone(request: Request, payload: PhoneAuthClaimPayload, db: AsyncSession, moysklad_client: MoySkladClient,) -> AuthTokensWithUserResponse | PhoneAuthVerificationRequiredResponse:
    await _apply_auth_rate_limit(request, scope="auth:phone_claim", principal=payload.phone_number)
    counterparty = await _get_counterparty_for_phone(payload.phone_number, moysklad_client)
    if counterparty is None: raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Counterparty was not found for this phone number")

    existing_phone_user = await get_user_by_phone_number(db, payload.phone_number)
    if existing_phone_user is not None and existing_phone_user.is_active and existing_phone_user.is_verified: raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Account already exists for this phone number")

    email = payload.email or _counterparty_email(counterparty) or (normalize_email(existing_phone_user.email) if existing_phone_user is not None else None)
    existing_email_user = await get_user_by_email(db, email)
    if (email and existing_email_user is not None and existing_email_user.is_active and (existing_phone_user is None or existing_email_user.id != existing_phone_user.id)): raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="User with this email already exists")

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
        else: target_user = await create_user(db, UserCreate(email=email, password_hash=password_hash, name=name, surname=surname, phone_number=payload.phone_number, is_verified=not bool(email), moysklad_counterparty_id=counterparty_id,), commit=False,)
        return await _finalize_phone_auth_setup(target_user, db)
    except IntegrityError as error:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="User with this phone number or email already exists") from error


async def register_user_by_phone(request: Request, payload: PhoneAuthRegisterPayload, db: AsyncSession, moysklad_client: MoySkladClient,) -> AuthTokensWithUserResponse | PhoneAuthVerificationRequiredResponse:
    await _apply_auth_rate_limit(request, scope="auth:phone_register", principal=payload.phone_number)
    existing_phone_user = await get_user_by_phone_number(db, payload.phone_number)
    if existing_phone_user is not None and existing_phone_user.is_active and existing_phone_user.is_verified: raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Account already exists for this phone number")

    counterparty = await _get_counterparty_for_phone(payload.phone_number, moysklad_client)
    if counterparty is not None: raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Counterparty already exists for this phone number")

    email = payload.email or (normalize_email(existing_phone_user.email) if existing_phone_user is not None else None)
    existing_email_user = await get_user_by_email(db, email)
    if (email and existing_email_user is not None and existing_email_user.is_active and (existing_phone_user is None or existing_email_user.id != existing_phone_user.id)): raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="User with this email already exists")

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
        else: target_user = await create_user(db, UserCreate(email=email, password_hash=password_hash, name=payload.name, surname=payload.surname, phone_number=payload.phone_number, is_verified=not bool(email),), commit=False,)
        return await _finalize_phone_auth_setup(target_user, db)
    except IntegrityError as error:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="User with this phone number or email already exists") from error


async def verify_phone_auth(request: Request, payload: PhoneAuthVerifyPayload, db: AsyncSession, moysklad_client: MoySkladClient) -> AuthTokensWithUserResponse:
    await _apply_auth_rate_limit(request, scope="auth:phone_verify", principal=payload.phone_number, verify=True)
    user = await get_user_by_phone_number(db, payload.phone_number)
    if user is None or not user.is_active or not user.email: raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired verification code")

    if user.is_verified: raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email is already verified")

    await _verify_latest_email_code(user, payload.code, db)
    user.is_verified = True
    await db.commit()
    await db.refresh(user)

    if user.moysklad_counterparty_id is not None:
        try: await moysklad_client.update_counterparty_email(user.moysklad_counterparty_id, user.email)
        except Exception: logger.exception("Failed to sync verified email back to MoySklad counterparty user_id=%s", user.id)

    return await _build_auth_tokens_response(user, db)


async def resend_phone_auth_verification_code(request: Request, payload: PhoneAuthCodeResendPayload, db: AsyncSession) -> PhoneAuthCodeSentResponse:
    await _apply_auth_rate_limit(request, scope="auth:phone_resend", principal=payload.phone_number)
    user = await get_user_by_phone_number(db, payload.phone_number)
    if user is None or not user.is_active or user.is_verified: raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found or already verified")
    if not user.email: raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email verification is unavailable for this account")

    try:
        await _create_and_send_verification_code(user, db)
        await db.commit()
    except (EmailVerificationConfigError, EmailVerificationDeliveryError) as error:
        logger.exception("Failed to resend phone auth verification code")
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Could not send verification email") from error

    return PhoneAuthCodeSentResponse(phone_number=payload.phone_number, email=user.email, message="Verification code sent")
