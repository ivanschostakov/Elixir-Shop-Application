from datetime import timedelta
from logging import getLogger
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status

from src.app.services.security import create_access_token
from config import REFRESH_TOKEN_LIFETIME_DAYS, ufa_now
from src.integrations.website_identity import WebsiteIdentityClient, get_website_identity_client
from src.app.services.security import hash_password, verify_password
from src.app.services.security.refresh import create_refresh_token, hash_refresh_token, verify_refresh_token
from src.app.services.website_identities.service import link_website_identity_to_user, login_with_website_identity
from src.database import get_db
from src.database.crud.auth.user import create_user, get_user_by_email, get_user_by_id, get_user_by_username
from src.database.crud.auth.user_session import create_user_session, get_user_session_by_id, update_user_session
from src.database.models.auth.user import User
from src.database.schemas.auth.user import UserCreate
from src.database.schemas.auth.user_session import UserSessionCreate, UserSessionUpdate
from src.database.schemas.website.website_identity import WebsiteIdentityRead

from .dependencies import get_current_user
from .schemas.login import UserLoginPayload
from .schemas.logout import UserLogoutPayload
from .schemas.refresh import UserRefreshPayload
from .schemas.register import UserRegisterPayload
from .schemas.responses import (
    AuthLogoutResponse,
    AuthRefreshResponse,
    AuthTokensWithUserResponse,
    AuthTokensWithWebsiteIdentityResponse,
    AuthUserRead,
)
from .schemas.website import WebsiteIdentityLoginPayload

logger = getLogger(__name__)
auth_router = APIRouter(prefix="/auth", tags=["auth"])


async def build_auth_tokens_response(user: User, db: AsyncSession) -> AuthTokensWithUserResponse:
    refresh_token = create_refresh_token()
    refresh_token_hash = hash_refresh_token(refresh_token)

    user_session_create = UserSessionCreate(user_id=user.id, refresh_token_hash=refresh_token_hash)
    session = await create_user_session(db, user_session_create)
    access_token = create_access_token(user_id=user.id, session_id=session.id)

    return AuthTokensWithUserResponse(
        access_token=access_token, refresh_token=refresh_token, session_id=session.id, user=AuthUserRead.model_validate(user)
    )


async def get_plain_login_user(payload: UserLoginPayload, db: AsyncSession) -> User:
    if payload.is_email: user = await get_user_by_email(db, payload.login)
    else: user = await get_user_by_username(db, payload.login)
    if not user or not user.is_active or not verify_password(payload.password, user.password_hash): raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    return user


@auth_router.post("/register", response_model=AuthTokensWithUserResponse, status_code=status.HTTP_201_CREATED)
async def register(payload: UserRegisterPayload, db: AsyncSession = Depends(get_db)) -> AuthTokensWithUserResponse:
    password_hash = hash_password(payload.password)
    user_create = UserCreate(username=payload.username, email=payload.email, name=payload.name, surname=payload.surname, password_hash=password_hash)

    try: user = await create_user(db, user_create)
    except IntegrityError as e:
        logger.exception("Failed to create user during registration")
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="User with this username or email already exists") from e

    return await build_auth_tokens_response(user, db)


@auth_router.post("/login", response_model=AuthTokensWithUserResponse, status_code=status.HTTP_200_OK, summary="Plain username or email login")
async def login(payload: UserLoginPayload, db: AsyncSession = Depends(get_db)) -> AuthTokensWithUserResponse:
    user = await get_plain_login_user(payload, db)
    return await build_auth_tokens_response(user, db)


@auth_router.post("/website/login", response_model=AuthTokensWithWebsiteIdentityResponse, status_code=status.HTTP_200_OK, summary="Website-backed login")
async def login_with_website(
    payload: WebsiteIdentityLoginPayload,
    db: AsyncSession = Depends(get_db),
    website_identity_client: WebsiteIdentityClient = Depends(get_website_identity_client),
) -> AuthTokensWithWebsiteIdentityResponse:
    user, website_identity = await login_with_website_identity(
        db,
        login=payload.login,
        password=payload.password,
        website_identity_client=website_identity_client,
    )
    auth_response = await build_auth_tokens_response(user, db)

    return AuthTokensWithWebsiteIdentityResponse(
        access_token=auth_response.access_token,
        refresh_token=auth_response.refresh_token,
        session_id=auth_response.session_id,
        user=auth_response.user,
        website_identity=WebsiteIdentityRead.model_validate(website_identity),
    )


@auth_router.post("/website/parse", response_model=WebsiteIdentityRead, status_code=status.HTTP_200_OK, summary="Refresh website identity data")
async def parse_website_identity(
    payload: WebsiteIdentityLoginPayload,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    website_identity_client: WebsiteIdentityClient = Depends(get_website_identity_client),
) -> WebsiteIdentityRead:
    website_identity = await link_website_identity_to_user(
        db,
        user=current_user,
        login=payload.login,
        password=payload.password,
        website_identity_client=website_identity_client,
    )
    return WebsiteIdentityRead.model_validate(website_identity)


@auth_router.post("/refresh", response_model=AuthRefreshResponse, status_code=status.HTTP_200_OK)
async def refresh(payload: UserRefreshPayload, db: AsyncSession = Depends(get_db)) -> AuthRefreshResponse:
    session = await get_user_session_by_id(db, payload.session_id)
    if not session:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Could not validate credentials")

    if session.revoked_at is not None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session has been revoked")

    if session.expires_at <= ufa_now():
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token has expired")

    ok = verify_refresh_token(payload.refresh_token, session.refresh_token_hash)
    if not ok:
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


@auth_router.post("/logout", response_model=AuthLogoutResponse, status_code=status.HTTP_200_OK)
async def logout(payload: UserLogoutPayload, db: AsyncSession = Depends(get_db)) -> AuthLogoutResponse:
    session = await get_user_session_by_id(db, payload.session_id)
    if not session:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Could not validate credentials")

    ok = verify_refresh_token(payload.refresh_token, session.refresh_token_hash)
    if not ok:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Could not validate credentials")

    if session.revoked_at is None:
        user_session_update = UserSessionUpdate(revoked_at=ufa_now())
        await update_user_session(db, session, user_session_update)

    return AuthLogoutResponse(ok=True, message="Logged out successfully")


@auth_router.get("/me", response_model=AuthUserRead, status_code=status.HTTP_200_OK)
async def me(current_user: User = Depends(get_current_user)) -> AuthUserRead:
    return AuthUserRead.model_validate(current_user)
