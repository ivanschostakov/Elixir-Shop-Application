import asyncio
import logging
import signal
from contextlib import suppress

from config import ONEC_SYNC_INTERVAL_MINUTES
from logger import setup_logging
from src.integrations.onec import sync_onec_product_catalog

log = logging.getLogger("worker.onec_sync")


async def _run_once() -> None:
    stats = await sync_onec_product_catalog()
    log.info("1C sync tick completed: %s", stats.as_dict())


async def run_forever() -> None:
    stop_event = asyncio.Event()
    interval_seconds = max(int(ONEC_SYNC_INTERVAL_MINUTES), 1) * 60

    async def _shutdown() -> None: stop_event.set()

    loop = asyncio.get_running_loop()
    for sig_name in ("SIGINT", "SIGTERM"):
        with suppress(AttributeError, NotImplementedError): loop.add_signal_handler(getattr(signal, sig_name), lambda: asyncio.create_task(_shutdown()))

    while not stop_event.is_set():
        try: await _run_once()
        except Exception: log.exception("1C sync tick failed")

        if stop_event.is_set(): break

        try: await asyncio.wait_for(stop_event.wait(), timeout=interval_seconds)
        except TimeoutError: continue


if __name__ == "__main__":
    setup_logging()
    asyncio.run(run_forever())
