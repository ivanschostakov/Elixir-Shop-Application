import getpass
import os
from contextlib import suppress
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlsplit
from config import TELEGRAM_COMMUNITY_CHAT_ID, TELEGRAM_USERBOT_API_HASH, TELEGRAM_USERBOT_API_ID, TELEGRAM_USERBOT_PHONE, TELEGRAM_USERBOT_PROXY_URL, TELEGRAM_USERBOT_SESSION_PATH


class TelegramUserbotConfigurationError(RuntimeError):
    pass


class TelegramUserbotAuthorizationError(RuntimeError):
    pass


def _session_file_path() -> Path:
    value = Path(TELEGRAM_USERBOT_SESSION_PATH)
    if value.suffix != ".session": value = Path(f"{value}.session")
    return value


def _ensure_session_directory() -> None:
    session_file = _session_file_path()
    session_file.parent.mkdir(parents=True, exist_ok=True)
    with suppress(OSError):
        os.chmod(session_file.parent, 0o700)


def _lock_down_session_file() -> None:
    with suppress(OSError):
        os.chmod(_session_file_path(), 0o600)


def _telethon_proxy() -> tuple[Any, ...] | None:
    raw = (TELEGRAM_USERBOT_PROXY_URL or "").strip()
    if not raw: return None
    parsed = urlsplit(raw)
    scheme = parsed.scheme.lower()
    if scheme not in {"http", "socks4", "socks5"} or not parsed.hostname: raise TelegramUserbotConfigurationError("TELEGRAM_USERBOT_PROXY_URL must be an HTTP, SOCKS4, or SOCKS5 URL")
    default_port = 8080 if scheme == "http" else 1080
    return (scheme, parsed.hostname, int(parsed.port or default_port), True, unquote(parsed.username) if parsed.username else None, unquote(parsed.password) if parsed.password else None,)


def _validate_configuration() -> None:
    if not TELEGRAM_USERBOT_API_ID or not TELEGRAM_USERBOT_API_HASH: raise TelegramUserbotConfigurationError("TELEGRAM_USERBOT_API_ID and TELEGRAM_USERBOT_API_HASH are required")
    if not TELEGRAM_COMMUNITY_CHAT_ID: raise TelegramUserbotConfigurationError("TELEGRAM_COMMUNITY_CHAT_ID is required")


def _build_client(*, receive_updates: bool = False):
    from telethon import TelegramClient

    _validate_configuration()
    _ensure_session_directory()
    return TelegramClient(str(TELEGRAM_USERBOT_SESSION_PATH), TELEGRAM_USERBOT_API_ID, str(TELEGRAM_USERBOT_API_HASH), proxy=_telethon_proxy(), receive_updates=receive_updates, request_retries=3, connection_retries=3, timeout=15, app_version="Elixir Community Bridge",)


async def _resolve_forum_peer(client: Any) -> Any:
    try: return await client.get_input_entity(TELEGRAM_COMMUNITY_CHAT_ID)
    except ValueError:
        async for dialog in client.iter_dialogs():
            if int(dialog.id) == int(TELEGRAM_COMMUNITY_CHAT_ID): return dialog.input_entity
    raise TelegramUserbotConfigurationError("The Telethon user is not a member of the configured community supergroup")


async def _require_authorized_user(client: Any) -> None:
    if not await client.is_user_authorized(): raise TelegramUserbotAuthorizationError("Telethon session is not authorized; run the telegram_userbot_login script")
    me = await client.get_me()
    if bool(getattr(me, "bot", False)): raise TelegramUserbotAuthorizationError("Telethon topic sync requires a user session, not a bot-token session")


async def authorize_telegram_userbot() -> int:
    """Interactively authorize the configured user and persist its session."""
    client = _build_client()
    phone = TELEGRAM_USERBOT_PHONE or (lambda: input("Telegram phone number: ").strip())
    await client.start(
        phone=phone,
        code_callback=lambda: input("Telegram login code: ").strip(),
        password=lambda: getpass.getpass("Telegram 2FA password: "),
    )
    try:
        me = await client.get_me()
        if me is None or bool(getattr(me, "bot", False)): raise TelegramUserbotAuthorizationError("A real Telegram user account is required")
        return int(me.id)
    finally:
        await client.disconnect()
        _lock_down_session_file()
