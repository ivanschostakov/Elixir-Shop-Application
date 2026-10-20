import hashlib
import hmac
import json
import time
from urllib.parse import parse_qsl
from fastapi import HTTPException
from starlette import status
from config import TELEGRAM_AUTH_MAX_AGE_SECONDS, TELEGRAM_BOT_TOKEN
from src.database.models.auth.user import User
from .utils import _fit_telegram_username, _telegram_config_unavailable


def _validate_telegram_init_data(init_data: str) -> dict[str, object]:
    if not TELEGRAM_BOT_TOKEN: raise _telegram_config_unavailable()

    pairs = parse_qsl(init_data, keep_blank_values=True, strict_parsing=False)
    values = dict(pairs)
    received_hash = values.pop("hash", "")
    if not received_hash: raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid Telegram auth data")

    data_check_string = "\n".join(f"{key}={value}" for key, value in sorted(values.items()))
    secret_key = hmac.new(b"WebAppData", TELEGRAM_BOT_TOKEN.encode("utf-8"), hashlib.sha256).digest()
    expected_hash = hmac.new(secret_key, data_check_string.encode("utf-8"), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected_hash, received_hash): raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid Telegram auth data")

    try: auth_date = int(values.get("auth_date", "0"))
    except (TypeError, ValueError): auth_date = 0
    if auth_date <= 0 or time.time() - auth_date > TELEGRAM_AUTH_MAX_AGE_SECONDS: raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Expired Telegram auth data")

    try: user = json.loads(values.get("user", "{}"))
    except (TypeError, json.JSONDecodeError) as error: raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid Telegram auth user") from error

    if not isinstance(user, dict): raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid Telegram auth user")
    try: telegram_user_id = int(user["id"])
    except (KeyError, TypeError, ValueError) as error: raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid Telegram auth user") from error
    if telegram_user_id <= 0: raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid Telegram auth user")

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
    return (user.is_active and user.telegram_user_id == telegram_user_id and user.telegram_phone_confirmed_at is not None and bool(user.phone_number))


def verify_telegram_init_data_for_user(init_data: str, user: User) -> tuple[bool, str | None]:
    try: telegram_user = _validate_telegram_init_data(init_data)
    except HTTPException as error: return False, str(error.detail)

    telegram_user_id = int(telegram_user["id"])
    if not _is_telegram_user_phone_confirmed(user, telegram_user_id): return False, "telegram user is not linked to the current user"

    return True, None
