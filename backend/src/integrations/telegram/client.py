import json
from pathlib import Path
from typing import Any

import httpx

from config import TELEGRAM_API_BASE_URL, TELEGRAM_BOT_TOKEN, TELEGRAM_PROXY_URL


class TelegramBotAPIError(RuntimeError):
    def __init__(self, message: str, *, error_code: int | None = None, retry_after: int | None = None) -> None:
        super().__init__(message)
        self.error_code = error_code
        self.retry_after = retry_after


class TelegramBotClient:
    def __init__(self) -> None:
        token = (TELEGRAM_BOT_TOKEN or "").strip()
        self.enabled = bool(token)
        self._base_url = f"{TELEGRAM_API_BASE_URL.rstrip('/')}/bot{token}" if token else ""
        self._file_base_url = f"{TELEGRAM_API_BASE_URL.rstrip('/')}/file/bot{token}" if token else ""

    async def call(self, method: str, *, data: dict[str, Any] | None = None, files: dict[str, tuple[str, bytes, str]] | None = None, timeout: float = 30.0) -> Any:
        if not self.enabled: raise TelegramBotAPIError("Telegram bot is not configured")
        encoded_data: dict[str, str] = {}
        for key, value in (data or {}).items():
            if value is None: continue
            if isinstance(value, (dict, list, tuple)): encoded_data[key] = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
            elif isinstance(value, bool): encoded_data[key] = "true" if value else "false"
            else: encoded_data[key] = str(value)

        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(timeout, connect=10.0), proxy=TELEGRAM_PROXY_URL) as client:
                response = await client.post(f"{self._base_url}/{method}", data=encoded_data, files=files)
        except httpx.TimeoutException as exc: raise TimeoutError(f"Telegram {method} request timed out") from exc
        except httpx.HTTPError as exc: raise TelegramBotAPIError(f"Telegram {method} request failed") from exc

        try: payload = response.json()
        except ValueError as exc: raise TelegramBotAPIError(f"Telegram {method} returned invalid JSON") from exc
        if not isinstance(payload, dict): raise TelegramBotAPIError(f"Telegram {method} returned an invalid response")
        if response.is_error or not payload.get("ok"):
            parameters = payload.get("parameters") if isinstance(payload.get("parameters"), dict) else {}
            retry_after = parameters.get("retry_after")
            raise TelegramBotAPIError(str(payload.get("description") or f"Telegram {method} failed"), error_code=int(payload.get("error_code") or response.status_code or 0) or None, retry_after=int(retry_after) if retry_after is not None else None)
        return payload.get("result")

    async def get_chat(self, chat_id: int) -> dict[str, Any]:
        result = await self.call("getChat", data={"chat_id": chat_id})
        return result if isinstance(result, dict) else {}

    async def get_chat_member(self, chat_id: int, user_id: int) -> dict[str, Any]:
        result = await self.call("getChatMember", data={"chat_id": chat_id, "user_id": user_id})
        return result if isinstance(result, dict) else {}

    async def get_user_profile_photo(self, user_id: int) -> dict[str, Any] | None:
        result = await self.call("getUserProfilePhotos", data={"user_id": user_id, "offset": 0, "limit": 1})
        photos = result.get("photos") if isinstance(result, dict) else None
        if not isinstance(photos, list) or not photos or not isinstance(photos[0], list): return None
        sizes = [size for size in photos[0] if isinstance(size, dict)]
        return max(sizes, key=lambda size: (int(size.get("file_size") or 0), int(size.get("width") or 0) * int(size.get("height") or 0)), default=None)

    async def download_file(self, file_id: str, destination: Path, *, max_bytes: int) -> int:
        file_info = await self.call("getFile", data={"file_id": file_id})
        if not isinstance(file_info, dict) or not file_info.get("file_path"): raise TelegramBotAPIError("Telegram file path is unavailable")
        if int(file_info.get("file_size") or 0) > max_bytes: raise TelegramBotAPIError("Telegram file exceeds the configured download limit", error_code=413)
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(60.0, connect=10.0), proxy=TELEGRAM_PROXY_URL) as client:
                async with client.stream("GET", f"{self._file_base_url}/{file_info['file_path']}") as response:
                    response.raise_for_status()
                    size = 0
                    with destination.open("wb") as target:
                        async for chunk in response.aiter_bytes():
                            size += len(chunk)
                            if size > max_bytes:
                                target.close(); destination.unlink(missing_ok=True)
                                raise TelegramBotAPIError("Telegram file exceeds the configured download limit", error_code=413)
                            target.write(chunk)
        except TelegramBotAPIError:
            raise
        except httpx.TimeoutException as exc:
            destination.unlink(missing_ok=True)
            raise TimeoutError("Telegram file download timed out") from exc
        except httpx.HTTPError as exc:
            destination.unlink(missing_ok=True)
            raise TelegramBotAPIError("Telegram file download failed") from exc
        except OSError:
            destination.unlink(missing_ok=True)
            raise
        return size

    async def delete_message(self, chat_id: int, message_id: int) -> None:
        await self.call("deleteMessage", data={"chat_id": chat_id, "message_id": message_id})


_telegram_bot_client = TelegramBotClient()


def get_telegram_bot_client() -> TelegramBotClient: return _telegram_bot_client
