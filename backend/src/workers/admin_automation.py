import asyncio
import logging
import signal

from contextlib import suppress

from config import ADMIN_AUTOMATION_INTERVAL_SECONDS
from logger import setup_logging
from src.app.services.admin.automation import process_order_automations_once
from src.app.services.admin.jobs import record_worker_heartbeat
from src.app.services.admin.sla import scan_sla_breaches
from src.database import get_session


log = logging.getLogger("worker.admin_automation")


async def _run_once() -> None:
    await record_worker_heartbeat("admin_automation")
    results = await process_order_automations_once()
    async with get_session() as session:
        sla_breaches = await scan_sla_breaches(session)
    if results["executed"] or results["failed"] or sla_breaches:
        log.info("automation tick completed rules=%s sla_breaches=%s", results, sla_breaches)


async def run_forever() -> None:
    stop_event = asyncio.Event()
    interval_seconds = max(int(ADMIN_AUTOMATION_INTERVAL_SECONDS), 15)

    def _shutdown() -> None:
        stop_event.set()

    loop = asyncio.get_running_loop()
    for sig_name in ("SIGINT", "SIGTERM"):
        with suppress(AttributeError, NotImplementedError):
            loop.add_signal_handler(getattr(signal, sig_name), _shutdown)

    while not stop_event.is_set():
        try:
            await _run_once()
        except Exception:
            log.exception("admin automation tick failed")
        if stop_event.is_set():
            break
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=interval_seconds)
        except TimeoutError:
            continue


if __name__ == "__main__":
    setup_logging()
    asyncio.run(run_forever())
