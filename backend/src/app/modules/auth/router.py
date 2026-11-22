from fastapi import APIRouter, BackgroundTasks, Depends, Request
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
from src.app.services.auth.service.password_reset import confirm_password_reset, request_password_reset, verify_password_reset
from src.database.models.auth.user import User

from .dependencies import get_current_user
from .schemas.login import UserLoginPayload, UserLoginVerifyPayload
from .schemas.logout import UserLogoutPayload
from .schemas.password_reset import (
    UserPasswordResetComplete, UserPasswordResetConfirm, UserPasswordResetRequest,
    UserPasswordResetResponse, UserPasswordResetVerified, UserPasswordResetVerify,
)
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
from pydantic import BaseModel, Field
from typing import Literal
from src.database.limits import PROMO_CODE_MAX_LENGTH

auth_router = APIRouter(prefix="/auth", tags=["auth"])


class RegistrationProgramChoice(BaseModel):
    program: Literal["bonus", "partner"]
    promo_code: str | None = Field(default=None, max_length=PROMO_CODE_MAX_LENGTH)


@auth_router.post("/registration-program", response_model=AuthUserRead)
async def registration_program(request: Request, payload: RegistrationProgramChoice, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    from fastapi import HTTPException
    from src.app.services.auth.service.counterparty import _link_moysklad_counterparty_by_email
    from src.app.services.referrals.registration import registration_choice_required, record_registration_choice, sync_registration_choice
    from src.app.services.auth.service.rate_limits import _apply_auth_rate_limit
    await _apply_auth_rate_limit(request, scope="auth:registration_program", principal=str(current_user.id))
    await _link_moysklad_counterparty_by_email(current_user, db)
    if not await registration_choice_required(db, user=current_user):
        # The endpoint cannot be used to switch an existing customer's program.
        if current_user.moysklad_counterparty_id is None:
            raise HTTPException(409, "Программа уже выбрана.")
        return AuthUserRead.model_validate(current_user)
    if payload.program == "bonus" and payload.promo_code:
        raise HTTPException(422, "Для бонусной программы промокод не используется.")
    await record_registration_choice(db, user=current_user, program=payload.program, promo_code=payload.promo_code)
    await db.commit()
    await sync_registration_choice(db, user=current_user)
    from src.app.services.benefits.loyalty import grant_welcome_bonus_safe
    await grant_welcome_bonus_safe(db, user=current_user)
    return AuthUserRead.model_validate(current_user)


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


@auth_router.post("/password-reset/request", response_model=UserPasswordResetResponse)
async def password_reset_request(
    request: Request, payload: UserPasswordResetRequest, tasks: BackgroundTasks, db: AsyncSession = Depends(get_db),
) -> UserPasswordResetResponse:
    await request_password_reset(db, request, tasks, email=str(payload.email))
    return UserPasswordResetResponse()


@auth_router.post("/password-reset/confirm", response_model=UserPasswordResetResponse)
async def password_reset_confirm(
    request: Request, payload: UserPasswordResetConfirm, db: AsyncSession = Depends(get_db),
) -> UserPasswordResetResponse:
    await confirm_password_reset(db, request, email=str(payload.email), code=payload.code, password=payload.password)
    return UserPasswordResetResponse()


@auth_router.post("/password-reset/verify", response_model=UserPasswordResetVerified)
async def password_reset_verify(
    request: Request, payload: UserPasswordResetVerify, db: AsyncSession = Depends(get_db),
) -> UserPasswordResetVerified:
    token = await verify_password_reset(db, request, email=str(payload.email), code=payload.code)
    return UserPasswordResetVerified(reset_token=token)


@auth_router.post("/password-reset/complete", response_model=UserPasswordResetResponse)
async def password_reset_complete(
    request: Request, payload: UserPasswordResetComplete, db: AsyncSession = Depends(get_db),
) -> UserPasswordResetResponse:
    await confirm_password_reset(db, request, email=str(payload.email), reset_token=payload.reset_token, password=payload.password)
    return UserPasswordResetResponse()


@auth_router.post("/telegram/session", response_model=AuthTokensWithUserResponse | TelegramAuthContactRequiredResponse, status_code=status.HTTP_200_OK)
async def telegram_session(request: Request, payload: TelegramAuthPayload, db: AsyncSession = Depends(get_db)) -> AuthTokensWithUserResponse | TelegramAuthContactRequiredResponse:
    return await login_user_by_telegram(request, payload, db)


@auth_router.post("/refresh", response_model=AuthRefreshResponse, status_code=status.HTTP_200_OK)
async def refresh(request: Request, payload: UserRefreshPayload, db: AsyncSession = Depends(get_db)) -> AuthRefreshResponse: return await refresh_user_tokens(request, payload, db)


@auth_router.post("/logout", response_model=AuthLogoutResponse, status_code=status.HTTP_200_OK)
async def logout(request: Request, payload: UserLogoutPayload, db: AsyncSession = Depends(get_db)) -> AuthLogoutResponse: return await logout_user_session(request, payload, db)


@auth_router.get("/me", response_model=AuthUserRead, status_code=status.HTTP_200_OK)
async def me(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)) -> AuthUserRead:
    from src.app.services.referrals.registration import registration_choice_required
    return AuthUserRead.model_validate(current_user).model_copy(update={
        "program_selection_required": await registration_choice_required(db, user=current_user)})


@auth_router.delete("/me", response_model=AuthLogoutResponse, status_code=status.HTTP_200_OK)
async def delete_my_account(request: Request, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)) -> AuthLogoutResponse: return await delete_user_account(request, current_user, db)
