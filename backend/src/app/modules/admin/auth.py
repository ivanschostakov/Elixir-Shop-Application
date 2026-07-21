from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status

from config import (
    ADMIN_ACCESS_EXPIRE_MINUTES,
    ADMIN_CHALLENGE_EXPIRE_MINUTES,
    ADMIN_COOKIE_SECURE,
    ADMIN_REFRESH_COOKIE_NAME,
    REFRESH_TOKEN_LIFETIME_DAYS,
    ufa_now,
)
from src.app.modules.admin.schemas import (
    AdminAuthResponse,
    AdminChallengeResponse,
    AdminLocalePayload,
    AdminLoginPayload,
    AdminMfaSetupPayload,
    AdminMfaSetupResponse,
    AdminMfaVerifyPayload,
    AdminOkResponse,
    AdminPrincipal,
    AdminSessionRead,
    AdminUserRead,
)
from src.app.services.admin.permissions import AdminContext, build_admin_context, get_admin_by_user_id, get_current_admin_context
from src.app.services.admin.security import (
    build_totp_uri,
    create_admin_access_token,
    create_admin_challenge_token,
    decrypt_totp_secret,
    decode_admin_token,
    encrypt_totp_secret,
    generate_totp_secret,
    verify_totp,
)
from src.app.services.rate_limit import client_ip_from_request, enforce_rate_limit
from src.app.services.security import verify_password
from src.app.services.security.refresh import create_refresh_token, hash_refresh_token, verify_refresh_token
from src.database import get_db
from src.database.models import Admin, User, UserSession

admin_auth_router = APIRouter(prefix="/auth", tags=["admin_auth"])


def _principal(context: AdminContext) -> AdminPrincipal:
    return AdminPrincipal(
        user=AdminUserRead(
            id=context.user.id,
            email=context.user.email,
            name=context.user.name,
            surname=context.user.surname,
            locale=context.admin.locale if context.admin.locale in {"ru", "en"} else "ru",
        ),
        roles=list(context.roles),
        permissions=sorted(context.permissions),
    )


def _set_refresh_cookie(response: Response, *, session_id: int, refresh_token: str) -> None:
    response.set_cookie(
        ADMIN_REFRESH_COOKIE_NAME,
        f"{session_id}.{refresh_token}",
        max_age=REFRESH_TOKEN_LIFETIME_DAYS * 24 * 60 * 60,
        path="/api/v1/admin",
        secure=ADMIN_COOKIE_SECURE,
        httponly=True,
        samesite="strict",
    )


def _clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(
        ADMIN_REFRESH_COOKIE_NAME,
        path="/api/v1/admin",
        secure=ADMIN_COOKIE_SECURE,
        httponly=True,
        samesite="strict",
    )


def _parse_refresh_cookie(request: Request) -> tuple[int, str]:
    raw = request.cookies.get(ADMIN_REFRESH_COOKIE_NAME, "")
    session_id_raw, separator, refresh_token = raw.partition(".")
    if not separator or not refresh_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Admin refresh session is missing")
    try:
        return int(session_id_raw), refresh_token
    except ValueError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Admin refresh session is invalid") from None


def _challenge_user_id(token: str, *, purpose: str) -> int:
    payload = decode_admin_token(token, expected_type="admin_challenge")
    if payload is None or payload.get("purpose") != purpose:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Admin challenge is invalid or expired")
    try:
        return int(payload["sub"])
    except (KeyError, TypeError, ValueError):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Admin challenge is invalid") from None


async def _load_active_admin(db: AsyncSession, user_id: int) -> Admin:
    admin = await get_admin_by_user_id(db, user_id)
    if admin is None or not admin.is_active or not admin.user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Admin account is unavailable")
    return admin


async def _issue_admin_session(
    db: AsyncSession,
    request: Request,
    response: Response,
    *,
    admin: Admin,
) -> AdminAuthResponse:
    now = ufa_now()
    refresh_token = create_refresh_token()
    session = UserSession(
        user_id=admin.user_id,
        refresh_token_hash=hash_refresh_token(refresh_token),
        expires_at=now + timedelta(days=REFRESH_TOKEN_LIFETIME_DAYS),
        last_used_at=now,
        user_agent=(request.headers.get("user-agent") or "")[:512] or None,
        ip_address=client_ip_from_request(request)[:64],
        purpose="admin",
        mfa_verified_at=now,
    )
    db.add(session)
    admin.last_login_at = now
    await db.commit()
    await db.refresh(session)
    admin = await _load_active_admin(db, admin.user_id)
    context = build_admin_context(admin=admin, session=session)
    _set_refresh_cookie(response, session_id=session.id, refresh_token=refresh_token)
    return AdminAuthResponse(
        access_token=create_admin_access_token(user_id=admin.user_id, session_id=session.id),
        expires_in=ADMIN_ACCESS_EXPIRE_MINUTES * 60,
        principal=_principal(context),
    )


@admin_auth_router.post("/login", response_model=AdminChallengeResponse)
async def login_admin(payload: AdminLoginPayload, request: Request, db: AsyncSession = Depends(get_db)) -> AdminChallengeResponse:
    await enforce_rate_limit(request, scope="admin:login", limit=10, window_seconds=60, key=f"{client_ip_from_request(request)}:{str(payload.email).lower()}")
    user = (await db.execute(select(User).where(User.email == str(payload.email).lower()))).scalar_one_or_none()
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")
    admin = await _load_active_admin(db, user.id)
    setup_required = admin.mfa_confirmed_at is None or not admin.totp_secret_encrypted
    return AdminChallengeResponse(
        status="mfa_setup_required" if setup_required else "mfa_required",
        challenge_token=create_admin_challenge_token(user_id=user.id, purpose="setup" if setup_required else "login"),
        expires_in=ADMIN_CHALLENGE_EXPIRE_MINUTES * 60,
    )


@admin_auth_router.post("/mfa/setup", response_model=AdminMfaSetupResponse)
async def setup_admin_mfa(payload: AdminMfaSetupPayload, db: AsyncSession = Depends(get_db)) -> AdminMfaSetupResponse:
    admin = await _load_active_admin(db, _challenge_user_id(payload.challenge_token, purpose="setup"))
    if admin.mfa_confirmed_at is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="MFA is already configured")
    secret = decrypt_totp_secret(admin.totp_secret_encrypted) if admin.totp_secret_encrypted else None
    if secret is None:
        secret = generate_totp_secret()
        admin.totp_secret_encrypted = encrypt_totp_secret(secret)
        await db.commit()
    email = admin.user.email or f"admin-{admin.user_id}"
    return AdminMfaSetupResponse(secret=secret, otpauth_uri=build_totp_uri(secret=secret, email=email))


@admin_auth_router.post("/mfa/confirm", response_model=AdminAuthResponse)
async def confirm_admin_mfa(payload: AdminMfaVerifyPayload, request: Request, response: Response, db: AsyncSession = Depends(get_db)) -> AdminAuthResponse:
    await enforce_rate_limit(request, scope="admin:mfa", limit=10, window_seconds=60)
    admin = await _load_active_admin(db, _challenge_user_id(payload.challenge_token, purpose="setup"))
    secret = decrypt_totp_secret(admin.totp_secret_encrypted or "")
    if secret is None or not verify_totp(secret, payload.code):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid authentication code")
    admin.mfa_confirmed_at = ufa_now()
    await db.commit()
    return await _issue_admin_session(db, request, response, admin=admin)


@admin_auth_router.post("/mfa/verify", response_model=AdminAuthResponse)
async def verify_admin_mfa(payload: AdminMfaVerifyPayload, request: Request, response: Response, db: AsyncSession = Depends(get_db)) -> AdminAuthResponse:
    await enforce_rate_limit(request, scope="admin:mfa", limit=10, window_seconds=60)
    admin = await _load_active_admin(db, _challenge_user_id(payload.challenge_token, purpose="login"))
    secret = decrypt_totp_secret(admin.totp_secret_encrypted or "")
    if secret is None or not verify_totp(secret, payload.code):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid authentication code")
    return await _issue_admin_session(db, request, response, admin=admin)


@admin_auth_router.post("/refresh", response_model=AdminAuthResponse)
async def refresh_admin_session(request: Request, response: Response, db: AsyncSession = Depends(get_db)) -> AdminAuthResponse:
    await enforce_rate_limit(request, scope="admin:refresh", limit=30, window_seconds=60)
    session_id, current_refresh_token = _parse_refresh_cookie(request)
    session = await db.get(UserSession, session_id)
    if (
        session is None
        or session.purpose != "admin"
        or session.revoked_at is not None
        or session.expires_at <= ufa_now()
        or not verify_refresh_token(current_refresh_token, session.refresh_token_hash)
    ):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Admin refresh session is invalid")
    admin = await _load_active_admin(db, session.user_id)
    if admin.mfa_confirmed_at is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="MFA is required")
    new_refresh_token = create_refresh_token()
    session.refresh_token_hash = hash_refresh_token(new_refresh_token)
    session.last_used_at = ufa_now()
    session.expires_at = ufa_now() + timedelta(days=REFRESH_TOKEN_LIFETIME_DAYS)
    await db.commit()
    context = build_admin_context(admin=admin, session=session)
    _set_refresh_cookie(response, session_id=session.id, refresh_token=new_refresh_token)
    return AdminAuthResponse(
        access_token=create_admin_access_token(user_id=admin.user_id, session_id=session.id),
        expires_in=ADMIN_ACCESS_EXPIRE_MINUTES * 60,
        principal=_principal(context),
    )


@admin_auth_router.get("/me", response_model=AdminPrincipal)
async def get_admin_me(context: AdminContext = Depends(get_current_admin_context)) -> AdminPrincipal:
    return _principal(context)


@admin_auth_router.patch("/me/locale", response_model=AdminPrincipal)
async def update_admin_locale(payload: AdminLocalePayload, db: AsyncSession = Depends(get_db), context: AdminContext = Depends(get_current_admin_context)) -> AdminPrincipal:
    context.admin.locale = payload.locale
    await db.commit()
    return _principal(build_admin_context(admin=context.admin, session=context.session))


@admin_auth_router.get("/sessions", response_model=list[AdminSessionRead])
async def list_admin_sessions(db: AsyncSession = Depends(get_db), context: AdminContext = Depends(get_current_admin_context)) -> list[AdminSessionRead]:
    rows = list((await db.execute(select(UserSession).where(UserSession.user_id == context.user.id, UserSession.purpose == "admin").order_by(UserSession.created_at.desc()))).scalars().all())
    return [AdminSessionRead(
        id=row.id,
        user_agent=row.user_agent,
        ip_address=row.ip_address,
        created_at=row.created_at,
        last_used_at=row.last_used_at,
        expires_at=row.expires_at,
        revoked_at=row.revoked_at,
        current=row.id == context.session.id,
    ) for row in rows]


@admin_auth_router.delete("/sessions/{session_id}", response_model=AdminOkResponse)
async def revoke_admin_session(session_id: int, db: AsyncSession = Depends(get_db), context: AdminContext = Depends(get_current_admin_context)) -> AdminOkResponse:
    target = await db.get(UserSession, session_id)
    if target is None or target.user_id != context.user.id or target.purpose != "admin":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    target.revoked_at = target.revoked_at or ufa_now()
    await db.commit()
    return AdminOkResponse()


@admin_auth_router.post("/logout", response_model=AdminOkResponse)
async def logout_admin(response: Response, db: AsyncSession = Depends(get_db), context: AdminContext = Depends(get_current_admin_context)) -> AdminOkResponse:
    context.session.revoked_at = context.session.revoked_at or ufa_now()
    await db.commit()
    _clear_refresh_cookie(response)
    return AdminOkResponse()
