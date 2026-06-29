from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status

from src.app.services.auth import (
    claim_user_by_phone,
    delete_user_account,
    login_user_by_phone,
    login_user_by_telegram,
    logout_user_session,
    parse_website_identity_for_user,
    refresh_user_tokens,
    register_user_by_phone,
    resend_phone_auth_verification_code,
    start_phone_auth,
    verify_phone_auth,
)
from src.database import get_db
from src.database.models.auth.user import User
from src.database.schemas.website.website_identity import WebsiteIdentityRead
from src.integrations.moysklad import MoySkladClient, get_moysklad_client
from src.integrations.website_identity import WebsiteIdentityClient, get_website_identity_client

from .dependencies import get_current_user
from .schemas.logout import UserLogoutPayload
from .schemas.phone import (
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
from .schemas.refresh import UserRefreshPayload
from .schemas.responses import (
    AuthLogoutResponse,
    AuthRefreshResponse,
    AuthTokensWithUserResponse,
    AuthUserRead,
)
from .schemas.telegram import TelegramAuthContactRequiredResponse, TelegramAuthPayload
from .schemas.website import WebsiteIdentityLoginPayload

auth_router = APIRouter(prefix="/auth", tags=["auth"])


@auth_router.post("/phone/start", response_model=PhoneAuthStartResponse, status_code=status.HTTP_200_OK)
async def phone_auth_start(request: Request, payload: PhoneAuthStartPayload, db: AsyncSession = Depends(get_db), moysklad_client: MoySkladClient = Depends(get_moysklad_client)) -> PhoneAuthStartResponse:
    return await start_phone_auth(request, payload, db, moysklad_client)


@auth_router.post("/phone/login", response_model=AuthTokensWithUserResponse, status_code=status.HTTP_200_OK)
async def phone_login(request: Request, payload: PhoneAuthLoginPayload, db: AsyncSession = Depends(get_db), moysklad_client: MoySkladClient = Depends(get_moysklad_client)) -> AuthTokensWithUserResponse:
    return await login_user_by_phone(request, payload, db, moysklad_client)


@auth_router.post("/phone/claim", response_model=AuthTokensWithUserResponse | PhoneAuthVerificationRequiredResponse, status_code=status.HTTP_200_OK)
async def phone_claim(request: Request, payload: PhoneAuthClaimPayload, db: AsyncSession = Depends(get_db), moysklad_client: MoySkladClient = Depends(get_moysklad_client)) -> AuthTokensWithUserResponse | PhoneAuthVerificationRequiredResponse:
    return await claim_user_by_phone(request, payload, db, moysklad_client)


@auth_router.post("/phone/register", response_model=AuthTokensWithUserResponse | PhoneAuthVerificationRequiredResponse, status_code=status.HTTP_200_OK)
async def phone_register(request: Request, payload: PhoneAuthRegisterPayload, db: AsyncSession = Depends(get_db), moysklad_client: MoySkladClient = Depends(get_moysklad_client)) -> AuthTokensWithUserResponse | PhoneAuthVerificationRequiredResponse:
    return await register_user_by_phone(request, payload, db, moysklad_client)


@auth_router.post("/phone/verify", response_model=AuthTokensWithUserResponse, status_code=status.HTTP_200_OK)
async def phone_verify(request: Request, payload: PhoneAuthVerifyPayload, db: AsyncSession = Depends(get_db), moysklad_client: MoySkladClient = Depends(get_moysklad_client)) -> AuthTokensWithUserResponse:
    return await verify_phone_auth(request, payload, db, moysklad_client)


@auth_router.post("/phone/resend-code", response_model=PhoneAuthCodeSentResponse, status_code=status.HTTP_200_OK)
async def resend_phone_verification_code(request: Request, payload: PhoneAuthCodeResendPayload, db: AsyncSession = Depends(get_db)) -> PhoneAuthCodeSentResponse:
    return await resend_phone_auth_verification_code(request, payload, db)


@auth_router.post("/telegram/session", response_model=AuthTokensWithUserResponse | TelegramAuthContactRequiredResponse, status_code=status.HTTP_200_OK)
async def telegram_session(request: Request, payload: TelegramAuthPayload, db: AsyncSession = Depends(get_db)) -> AuthTokensWithUserResponse | TelegramAuthContactRequiredResponse:
    return await login_user_by_telegram(request, payload, db)


@auth_router.post("/website/parse", response_model=WebsiteIdentityRead, status_code=status.HTTP_200_OK, summary="Refresh website identity data")
async def parse_website_identity(request: Request, payload: WebsiteIdentityLoginPayload, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db), website_identity_client: WebsiteIdentityClient = Depends(get_website_identity_client)) -> WebsiteIdentityRead: return await parse_website_identity_for_user(request, payload, current_user, db, website_identity_client)


@auth_router.post("/refresh", response_model=AuthRefreshResponse, status_code=status.HTTP_200_OK)
async def refresh(request: Request, payload: UserRefreshPayload, db: AsyncSession = Depends(get_db)) -> AuthRefreshResponse: return await refresh_user_tokens(request, payload, db)


@auth_router.post("/logout", response_model=AuthLogoutResponse, status_code=status.HTTP_200_OK)
async def logout(request: Request, payload: UserLogoutPayload, db: AsyncSession = Depends(get_db)) -> AuthLogoutResponse: return await logout_user_session(request, payload, db)


@auth_router.get("/me", response_model=AuthUserRead, status_code=status.HTTP_200_OK)
async def me(current_user: User = Depends(get_current_user)) -> AuthUserRead: return AuthUserRead.model_validate(current_user)


@auth_router.delete("/me", response_model=AuthLogoutResponse, status_code=status.HTTP_200_OK)
async def delete_my_account(request: Request, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)) -> AuthLogoutResponse: return await delete_user_account(request, current_user, db)
