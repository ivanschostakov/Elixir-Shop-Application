import asyncio
import logging
import signal
from contextlib import suppress
from datetime import datetime, timezone

from config import WEBSITE_CATALOG_SYNC_INTERVAL_MINUTES
from logger import setup_logging
from src.database import SessionLocal
from src.database.models import IntegrationRun
from src.integrations.website_catalog import (
    sync_catalog_content_with_website,
    website_catalog_sync_configured,
)


log = logging.getLogger("worker.website_catalog_sync")


async def _run_once() -> None:
    if not website_catalog_sync_configured():
        log.warning("Website catalog sync is disabled because endpoint or shared secret is missing")
        return
    async with SessionLocal() as db:
        run = IntegrationRun(
            provider="website_catalog",
            operation="product_content_sync",
            status="running",
            attempts=1,
            max_attempts=1,
            input_json={},
            counters_json={},
        )
        db.add(run)
        await db.commit()
        run_id = run.id
    try:
        async with SessionLocal() as db:
            stats = await sync_catalog_content_with_website(db)
        async with SessionLocal() as db:
            run = await db.get(IntegrationRun, run_id)
            if run is not None:
                run.status = "success"
                run.counters_json = stats.as_dict()
                run.finished_at = datetime.now(timezone.utc)
                await db.commit()
        log.info("Website catalog sync tick completed: %s", stats.as_dict())
    except Exception as error:
        async with SessionLocal() as db:
            run = await db.get(IntegrationRun, run_id)
            if run is not None:
                run.status = "error"
                run.error = str(error)[:8000]
                run.finished_at = datetime.now(timezone.utc)
                await db.commit()
        raise


async def run_forever() -> None:
    stop_event = asyncio.Event()
    interval_seconds = max(int(WEBSITE_CATALOG_SYNC_INTERVAL_MINUTES), 1) * 60
    loop = asyncio.get_running_loop()
    for signal_name in ("SIGINT", "SIGTERM"):
        with suppress(AttributeError, NotImplementedError):
            loop.add_signal_handler(getattr(signal, signal_name), stop_event.set)

    while not stop_event.is_set():
        try:
            await _run_once()
        except Exception:
            log.exception("Website catalog sync tick failed")
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=interval_seconds)
        except TimeoutError:
            continue


if __name__ == "__main__":
    setup_logging()
    asyncio.run(run_forever())
