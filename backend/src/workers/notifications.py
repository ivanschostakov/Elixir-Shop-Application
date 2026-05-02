import asyncio
import logging
import signal
from contextlib import suppress

from config import NOTIFICATION_SCAN_INTERVAL_MINUTES
from logger import setup_logging
from src.app.services.notifications import run_notification_processors_once
from src.database import get_session

log = logging.getLogger("worker.notifications")


async def _run_once() -> None:
    async with get_session() as session:
        results = await run_notification_processors_once(session)
    log.info("notification tick completed: %s", results)


async def run_forever() -> None:
    stop_event = asyncio.Event()
    interval_seconds = max(int(NOTIFICATION_SCAN_INTERVAL_MINUTES), 1) * 60

    async def _shutdown() -> None:
        stop_event.set()

    loop = asyncio.get_running_loop()
    for sig_name in ("SIGINT", "SIGTERM"):
        with suppress(AttributeError, NotImplementedError):
            loop.add_signal_handler(getattr(signal, sig_name), lambda: asyncio.create_task(_shutdown()))

    while not stop_event.is_set():
        try:
            await _run_once()
        except Exception:
            log.exception("notification tick failed")

        if stop_event.is_set():
            break

        try:
            await asyncio.wait_for(stop_event.wait(), timeout=interval_seconds)
        except TimeoutError:
            continue


if __name__ == "__main__":
    setup_logging()
    asyncio.run(run_forever())
