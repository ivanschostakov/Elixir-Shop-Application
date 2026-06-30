import asyncio
import logging
import signal
from contextlib import suppress
from typing import Any

import httpx

from config import (
    TELEGRAM_API_BASE_URL,
    TELEGRAM_BOT_TOKEN,
    TELEGRAM_POLLING_INTERVAL_SECONDS,
    TELEGRAM_POLLING_TIMEOUT_SECONDS,
    TELEGRAM_PROXY_URL,
)
from logger import setup_logging
from src.app.services.telegram_updates import process_telegram_update
from src.database import get_session

log = logging.getLogger("worker.telegram_polling")


class TelegramPollingClient:
    def __init__(self) -> None:
        if not TELEGRAM_BOT_TOKEN:
            raise RuntimeError("TELEGRAM_BOT_TOKEN is required for Telegram polling")
        self._base_url = f"{TELEGRAM_API_BASE_URL.rstrip('/')}/bot{TELEGRAM_BOT_TOKEN}"
        timeout = httpx.Timeout(
            connect=10.0,
            read=float(TELEGRAM_POLLING_TIMEOUT_SECONDS + 10),
            write=10.0,
            pool=10.0,
        )
        self._client = httpx.AsyncClient(base_url=self._base_url, timeout=timeout, proxy=TELEGRAM_PROXY_URL)

    async def aclose(self) -> None:
        await self._client.aclose()

    async def delete_webhook(self) -> None:
        response = await self._client.post("/deleteWebhook", data={"drop_pending_updates": "false"})
        response.raise_for_status()
        payload = response.json()
        if not payload.get("ok"):
            raise RuntimeError(f"Telegram deleteWebhook failed: {payload!r}")

    async def get_updates(self, offset: int | None) -> list[dict[str, Any]]:
        data: dict[str, str] = {
            "timeout": str(max(int(TELEGRAM_POLLING_TIMEOUT_SECONDS), 1)),
            "allowed_updates": '["message"]',
        }
        if offset is not None:
            data["offset"] = str(offset)
        response = await self._client.post("/getUpdates", data=data)
        response.raise_for_status()
        payload = response.json()
        if not payload.get("ok"):
            raise RuntimeError(f"Telegram getUpdates failed: {payload!r}")
        updates = payload.get("result") or []
        if not isinstance(updates, list):
            return []
        return [update for update in updates if isinstance(update, dict)]


async def run_forever() -> None:
    stop_event = asyncio.Event()
    interval_seconds = max(float(TELEGRAM_POLLING_INTERVAL_SECONDS), 0.2)
    failure_interval_seconds = max(interval_seconds, 5.0)
    offset: int | None = None
    client = TelegramPollingClient()
    is_webhook_deleted = False

    async def _shutdown() -> None:
        stop_event.set()

    loop = asyncio.get_running_loop()
    for sig_name in ("SIGINT", "SIGTERM"):
        with suppress(AttributeError, NotImplementedError):
            loop.add_signal_handler(getattr(signal, sig_name), lambda: asyncio.create_task(_shutdown()))

    try:
        while not stop_event.is_set():
            try:
                if not is_webhook_deleted:
                    await client.delete_webhook()
                    is_webhook_deleted = True
                    log.info("telegram webhook disabled; polling started proxy_enabled=%s", bool(TELEGRAM_PROXY_URL))

                updates = await client.get_updates(offset)
                for update in updates:
                    update_id = int(update.get("update_id") or 0)
                    async with get_session() as session:
                        result = await process_telegram_update(session, update)
                    log.info("telegram update processed update_id=%s result=%s", update_id, result)
                    if update_id > 0:
                        offset = update_id + 1
            except Exception:
                log.exception("telegram polling tick failed")
                try:
                    await asyncio.wait_for(stop_event.wait(), timeout=failure_interval_seconds)
                except TimeoutError:
                    continue

            if stop_event.is_set():
                break

            try:
                await asyncio.wait_for(stop_event.wait(), timeout=interval_seconds)
            except TimeoutError:
                continue
    finally:
        await client.aclose()


if __name__ == "__main__":
    setup_logging()
    asyncio.run(run_forever())
