from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status

from src.app.services.auth import (
    delete_user_account,
    login_user,
    login_user_by_telegram,
    logout_user_session,
    refresh_user_tokens,
    register_user,
    resend_login_verification_code,
    resend_registration_verification_code,
    verify_login_user,
    verify_registration_user,
)
from src.database import get_db
from src.database.models.auth.user import User

from .dependencies import get_current_user
from .schemas.login import UserLoginPayload, UserLoginVerifyPayload
from .schemas.logout import UserLogoutPayload
from .schemas.register import (
    UserRegisterPayload,
    UserRegisterVerifyPayload,
    UserRegistrationStartedResponse,
    UserVerificationCodeResendPayload,
    UserVerificationCodeSentResponse,
)
from .schemas.refresh import UserRefreshPayload
from .schemas.responses import (
    AuthLogoutResponse,
    AuthRefreshResponse,
    AuthTokensWithUserResponse,
    AuthUserRead,
    AuthVerificationRequiredResponse,
)
from .schemas.telegram import TelegramAuthContactRequiredResponse, TelegramAuthPayload

auth_router = APIRouter(prefix="/auth", tags=["auth"])


@auth_router.post("/register", response_model=UserRegistrationStartedResponse, status_code=status.HTTP_201_CREATED)
async def register(request: Request, payload: UserRegisterPayload, db: AsyncSession = Depends(get_db)) -> UserRegistrationStartedResponse:
    return await register_user(request, payload, db)


@auth_router.post("/register/verify", response_model=AuthTokensWithUserResponse, status_code=status.HTTP_200_OK)
async def verify_registration(request: Request, payload: UserRegisterVerifyPayload, db: AsyncSession = Depends(get_db)) -> AuthTokensWithUserResponse:
    return await verify_registration_user(request, payload, db)


@auth_router.post("/register/resend-code", response_model=UserVerificationCodeSentResponse, status_code=status.HTTP_200_OK)
async def resend_registration_code(request: Request, payload: UserVerificationCodeResendPayload, db: AsyncSession = Depends(get_db)) -> UserVerificationCodeSentResponse:
    return await resend_registration_verification_code(request, payload, db)


@auth_router.post("/login", response_model=AuthTokensWithUserResponse | AuthVerificationRequiredResponse, status_code=status.HTTP_200_OK)
async def login(request: Request, payload: UserLoginPayload, db: AsyncSession = Depends(get_db)) -> AuthTokensWithUserResponse | AuthVerificationRequiredResponse:
    return await login_user(request, payload, db)


@auth_router.post("/login/verify", response_model=AuthTokensWithUserResponse, status_code=status.HTTP_200_OK)
async def verify_login(request: Request, payload: UserLoginVerifyPayload, db: AsyncSession = Depends(get_db)) -> AuthTokensWithUserResponse:
    return await verify_login_user(request, payload, db)


@auth_router.post("/login/resend-code", response_model=AuthVerificationRequiredResponse, status_code=status.HTTP_200_OK)
async def resend_login_code(request: Request, payload: UserLoginPayload, db: AsyncSession = Depends(get_db)) -> AuthVerificationRequiredResponse:
    return await resend_login_verification_code(request, payload, db)


@auth_router.post("/telegram/session", response_model=AuthTokensWithUserResponse | TelegramAuthContactRequiredResponse, status_code=status.HTTP_200_OK)
async def telegram_session(request: Request, payload: TelegramAuthPayload, db: AsyncSession = Depends(get_db)) -> AuthTokensWithUserResponse | TelegramAuthContactRequiredResponse:
    return await login_user_by_telegram(request, payload, db)


@auth_router.post("/refresh", response_model=AuthRefreshResponse, status_code=status.HTTP_200_OK)
async def refresh(request: Request, payload: UserRefreshPayload, db: AsyncSession = Depends(get_db)) -> AuthRefreshResponse: return await refresh_user_tokens(request, payload, db)


@auth_router.post("/logout", response_model=AuthLogoutResponse, status_code=status.HTTP_200_OK)
async def logout(request: Request, payload: UserLogoutPayload, db: AsyncSession = Depends(get_db)) -> AuthLogoutResponse: return await logout_user_session(request, payload, db)


@auth_router.get("/me", response_model=AuthUserRead, status_code=status.HTTP_200_OK)
async def me(current_user: User = Depends(get_current_user)) -> AuthUserRead: return AuthUserRead.model_validate(current_user)


@auth_router.delete("/me", response_model=AuthLogoutResponse, status_code=status.HTTP_200_OK)
async def delete_my_account(request: Request, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)) -> AuthLogoutResponse: return await delete_user_account(request, current_user, db)
