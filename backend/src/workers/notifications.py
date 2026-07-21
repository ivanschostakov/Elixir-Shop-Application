import asyncio
import logging
import signal
from contextlib import suppress

from config import COMMUNITY_NOTIFICATION_SCAN_INTERVAL_SECONDS, NOTIFICATION_SCAN_INTERVAL_MINUTES
from logger import setup_logging
from src.app.services.notifications.core import process_community_message_notifications, run_notification_processors_once
from src.database import get_session

log = logging.getLogger("worker.notifications")


async def _run_once() -> None:
    async with get_session() as session: results = await run_notification_processors_once(session)
    log.info("notification tick completed: %s", results)


async def _run_community_once() -> None:
    async with get_session() as session:
        processed = await process_community_message_notifications(session)
    if processed:
        log.info("community notification tick completed processed=%s", processed)


async def run_forever() -> None:
    stop_event = asyncio.Event()
    interval_seconds = max(int(NOTIFICATION_SCAN_INTERVAL_MINUTES), 1) * 60
    community_interval_seconds = max(float(COMMUNITY_NOTIFICATION_SCAN_INTERVAL_SECONDS), 1.0)

    async def _shutdown() -> None: stop_event.set()

    loop = asyncio.get_running_loop()
    for sig_name in ("SIGINT", "SIGTERM"):
        with suppress(AttributeError, NotImplementedError): loop.add_signal_handler(getattr(signal, sig_name), lambda: asyncio.create_task(_shutdown()))

    async def _run_marketing_loop() -> None:
        while not stop_event.is_set():
            try: await _run_once()
            except Exception: log.exception("notification tick failed")
            if stop_event.is_set(): break
            try: await asyncio.wait_for(stop_event.wait(), timeout=interval_seconds)
            except TimeoutError: continue

    async def _run_community_loop() -> None:
        while not stop_event.is_set():
            try: await _run_community_once()
            except Exception: log.exception("community notification tick failed")
            if stop_event.is_set(): break
            try: await asyncio.wait_for(stop_event.wait(), timeout=community_interval_seconds)
            except TimeoutError: continue

    await asyncio.gather(_run_marketing_loop(), _run_community_loop())


if __name__ == "__main__":
    setup_logging()
    asyncio.run(run_forever())
