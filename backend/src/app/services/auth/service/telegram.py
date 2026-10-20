import secrets
from fastapi import Request
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from config import ufa_now
from src.app.modules.auth.schemas.responses import AuthTokensWithUserResponse
from src.app.modules.auth.schemas.telegram import TelegramAuthContactRequiredResponse, TelegramAuthPayload
from src.app.services.security import hash_password
from src.database.crud.auth.user import create_user, get_user_by_phone_number, get_user_by_telegram_user_id
from src.database.models.auth.user import User
from src.database.schemas.auth.user import UserCreate
from src.integrations.moysklad import MoySkladClient
from src.normalize import coerce_uuid
from .common import logger
from .utils import _fit_person_name, _fit_telegram_username, _normalize_telegram_phone
from .telegram_identity import _apply_telegram_profile, _is_telegram_user_phone_confirmed, _validate_telegram_init_data
from .rate_limits import _apply_auth_rate_limit
from .counterparty import _get_counterparty_for_phone, _sync_phone_identity_from_counterparty
from .sessions import _build_auth_tokens_response


async def login_user_by_telegram(request: Request, payload: TelegramAuthPayload, db: AsyncSession,) -> AuthTokensWithUserResponse | TelegramAuthContactRequiredResponse:
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


async def link_telegram_contact_to_user(db: AsyncSession, *, telegram_user_id: int, phone_number: str, first_name: object = None, last_name: object = None, username: object = None, moysklad_client: MoySkladClient | None = None,) -> tuple[User | None, str | None]:
    normalized_phone = _normalize_telegram_phone(phone_number)
    if telegram_user_id <= 0: return None, "invalid_telegram_user"
    if not normalized_phone: return None, "invalid_phone"

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
        try: counterparty = await _get_counterparty_for_phone(normalized_phone, moysklad_client)
        except Exception:
            logger.exception("Failed to resolve MoySklad counterparty for Telegram phone")
            counterparty = None
    counterparty_id = coerce_uuid(counterparty.get("id")) if isinstance(counterparty, dict) else None

    if (user_by_phone is not None and user_by_phone.telegram_user_id is not None and user_by_phone.telegram_user_id != telegram_user_id): return None, "phone_already_linked_to_another_telegram_user"

    if user_by_telegram is not None and user_by_phone is not None and user_by_telegram.id != user_by_phone.id: return None, "telegram_user_and_phone_belong_to_different_users"

    target_user = user_by_telegram or user_by_phone

    try:
        if target_user is None: target_user = await create_user(db, UserCreate(email=None, password_hash=hash_password(secrets.token_urlsafe(32)), name=_fit_person_name(first_name, "Telegram"), surname=_fit_person_name(last_name, "User"), phone_number=normalized_phone, is_verified=True, moysklad_counterparty_id=counterparty_id, telegram_user_id=telegram_user_id, telegram_username=_fit_telegram_username(username), telegram_phone_confirmed_at=now,), commit=False,)
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
