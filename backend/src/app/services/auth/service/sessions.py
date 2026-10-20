from datetime import timedelta
from fastapi import HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status
from config import USER_REFRESH_TOKEN_LIFETIME_DAYS, ufa_now
from src.app.modules.auth.schemas.logout import UserLogoutPayload
from src.app.modules.auth.schemas.refresh import UserRefreshPayload
from src.app.modules.auth.schemas.responses import AuthLogoutResponse, AuthRefreshResponse, AuthTokensWithUserResponse, AuthUserRead
from src.app.services.security import create_access_token
from src.app.services.security.refresh import create_refresh_token, hash_refresh_token, verify_refresh_token
from src.app.services.benefits.loyalty import grant_welcome_bonus_safe
from src.database.crud.auth.user import get_user_by_id
from src.database.crud.auth.user_session import create_user_session, get_user_session_by_id, update_user_session
from src.database.models.auth.user import User
from src.database.schemas.auth.user_session import UserSessionCreate, UserSessionUpdate
from .common import logger
from .rate_limits import _apply_auth_rate_limit
from .counterparty import _link_moysklad_counterparty_by_email


async def _build_auth_tokens_response(user: User, db: AsyncSession) -> AuthTokensWithUserResponse:
    await _link_moysklad_counterparty_by_email(user, db)
    user_id = user.id
    try: await grant_welcome_bonus_safe(db, user=user)
    except Exception:
        await db.rollback()
        await db.refresh(user)
        logger.exception("Failed to enqueue welcome bonus during authentication user_id=%s", user_id)
    refresh_token = create_refresh_token()
    refresh_token_hash = hash_refresh_token(refresh_token)
    session = await create_user_session(db, UserSessionCreate(user_id=user.id, refresh_token_hash=refresh_token_hash))
    access_token = create_access_token(user_id=user.id, session_id=session.id)
    return AuthTokensWithUserResponse(access_token=access_token, refresh_token=refresh_token, session_id=session.id, user=AuthUserRead.model_validate(user),)


async def refresh_user_tokens(request: Request, payload: UserRefreshPayload, db: AsyncSession) -> AuthRefreshResponse:
    await _apply_auth_rate_limit(request, scope="auth:refresh", principal=str(payload.session_id), verify=True)
    session = await get_user_session_by_id(db, payload.session_id)
    if not session or session.purpose != "app": raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Could not validate credentials")
    if session.revoked_at is not None: raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session has been revoked")
    if session.expires_at <= ufa_now(): raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token has expired")
    if not verify_refresh_token(payload.refresh_token, session.refresh_token_hash): raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Could not validate credentials")

    user = await get_user_by_id(db, session.user_id)
    if user is None or not user.is_active: raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Could not validate credentials")

    new_refresh_token = create_refresh_token()
    await update_user_session(
        db,
        session,
        UserSessionUpdate(
            refresh_token_hash=hash_refresh_token(new_refresh_token),
            last_used_at=ufa_now(),
            expires_at=ufa_now() + timedelta(days=USER_REFRESH_TOKEN_LIFETIME_DAYS),
        ),
    )
    access_token = create_access_token(user_id=user.id, session_id=session.id)
    return AuthRefreshResponse(access_token=access_token, refresh_token=new_refresh_token, session_id=session.id)


async def logout_user_session(request: Request, payload: UserLogoutPayload, db: AsyncSession) -> AuthLogoutResponse:
    await _apply_auth_rate_limit(request, scope="auth:logout", principal=str(payload.session_id), verify=True)
    session = await get_user_session_by_id(db, payload.session_id)
    if not session or session.purpose != "app": raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Could not validate credentials")
    if not verify_refresh_token(payload.refresh_token, session.refresh_token_hash): raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Could not validate credentials")

    if session.revoked_at is None: await update_user_session(db, session, UserSessionUpdate(revoked_at=ufa_now()))
    return AuthLogoutResponse(ok=True, message="Logged out successfully")


async def delete_user_account(request: Request, current_user: User, db: AsyncSession) -> AuthLogoutResponse:
    await _apply_auth_rate_limit(request, scope="auth:delete_account", principal=str(current_user.id), verify=True)

    from src.app.services.auth.account_erasure import erase_account
    await erase_account(db, current_user)
    return AuthLogoutResponse(ok=True, message="Account deleted")
