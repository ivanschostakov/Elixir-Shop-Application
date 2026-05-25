from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status

from src.app.services.auth import (
    delete_user_account,
    login_user,
    login_user_with_website,
    logout_user_session,
    parse_website_identity_for_user,
    refresh_user_tokens,
    register_user,
    resend_login_verification_code as resend_login_verification_code_service,
    resend_registration_verification_code as resend_registration_verification_code_service,
    verify_login_user,
    verify_registration_user,
)
from src.database import get_db
from src.database.models.auth.user import User
from src.database.schemas.website.website_identity import WebsiteIdentityRead
from src.app.services.email_verification import generate_email_verification_code, send_user_verification_code_email
from src.integrations.website_identity import WebsiteIdentityClient, get_website_identity_client

from .dependencies import get_current_user
from .schemas.login import UserLoginPayload, UserLoginVerifyPayload
from .schemas.logout import UserLogoutPayload
from .schemas.refresh import UserRefreshPayload
from .schemas.register import (
    UserRegisterPayload,
    UserRegisterVerifyPayload,
    UserRegistrationStartedResponse,
    UserVerificationCodeResendPayload,
    UserVerificationCodeSentResponse,
)
from .schemas.responses import (
    AuthLogoutResponse,
    AuthRefreshResponse,
    AuthTokensWithUserResponse,
    AuthTokensWithWebsiteIdentityResponse,
    AuthUserRead,
    AuthVerificationRequiredResponse,
)
from .schemas.website import WebsiteIdentityLoginPayload

auth_router = APIRouter(prefix="/auth", tags=["auth"])


@auth_router.post("/register", response_model=UserRegistrationStartedResponse, status_code=status.HTTP_201_CREATED)
async def register(request: Request, payload: UserRegisterPayload, db: AsyncSession = Depends(get_db)) -> UserRegistrationStartedResponse: return await register_user(request, payload, db)


@auth_router.post("/register/verify", response_model=AuthTokensWithUserResponse, status_code=status.HTTP_200_OK)
async def verify_registration(request: Request, payload: UserRegisterVerifyPayload, db: AsyncSession = Depends(get_db)) -> AuthTokensWithUserResponse: return await verify_registration_user(request, payload, db)


@auth_router.post("/register/resend-code", response_model=UserVerificationCodeSentResponse, status_code=status.HTTP_200_OK)
async def resend_registration_verification_code(request: Request, payload: UserVerificationCodeResendPayload, db: AsyncSession = Depends(get_db)) -> UserVerificationCodeSentResponse: return await resend_registration_verification_code_service(request, payload, db)


@auth_router.post("/login", response_model=AuthTokensWithUserResponse | AuthVerificationRequiredResponse, status_code=status.HTTP_200_OK, summary="Plain username login")
async def login(request: Request, payload: UserLoginPayload, db: AsyncSession = Depends(get_db), website_identity_client: WebsiteIdentityClient = Depends(get_website_identity_client)) -> AuthTokensWithUserResponse | AuthVerificationRequiredResponse: return await login_user(request, payload, db, website_identity_client)


@auth_router.post("/login/verify", response_model=AuthTokensWithUserResponse, status_code=status.HTTP_200_OK)
async def verify_login(request: Request, payload: UserLoginVerifyPayload, db: AsyncSession = Depends(get_db)) -> AuthTokensWithUserResponse: return await verify_login_user(request, payload, db)


@auth_router.post("/login/resend-code", response_model=AuthVerificationRequiredResponse, status_code=status.HTTP_200_OK)
async def resend_login_verification_code(request: Request, payload: UserLoginPayload, db: AsyncSession = Depends(get_db)) -> AuthVerificationRequiredResponse: return await resend_login_verification_code_service(request, payload, db)


@auth_router.post("/website/login", response_model=AuthTokensWithWebsiteIdentityResponse, status_code=status.HTTP_200_OK, summary="Website-backed login")
async def login_with_website(request: Request, payload: WebsiteIdentityLoginPayload, db: AsyncSession = Depends(get_db), website_identity_client: WebsiteIdentityClient = Depends(get_website_identity_client)) -> AuthTokensWithWebsiteIdentityResponse:
    return await login_user_with_website(request, payload, db, website_identity_client)


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
