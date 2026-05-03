import asyncio
import logging
import os
import signal
from contextlib import suppress

from logger import setup_logging
from src.integrations.bitrix import bitrix_sync_api_client
from src.scripts.sync_website_identities_from_bitrix_vm import run_sync

log = logging.getLogger("worker.website_identity_sync")


def _int_env(name: str, default: int) -> int:
    raw = (os.getenv(name) or "").strip()
    if not raw: return default
    try: return int(raw)
    except ValueError: return default


WEBSITE_IDENTITY_SYNC_INTERVAL_MINUTES = _int_env("WEBSITE_IDENTITY_SYNC_INTERVAL_MINUTES", 60)
WEBSITE_IDENTITY_SYNC_STALE_MINUTES = _int_env("WEBSITE_IDENTITY_SYNC_STALE_MINUTES", 50)
WEBSITE_IDENTITY_SYNC_BATCH_SIZE = _int_env("WEBSITE_IDENTITY_SYNC_BATCH_SIZE", 50)
WEBSITE_IDENTITY_SYNC_LIMIT = _int_env("WEBSITE_IDENTITY_SYNC_LIMIT", 0)
WEBSITE_IDENTITY_SYNC_DRY_RUN = (os.getenv("WEBSITE_IDENTITY_SYNC_DRY_RUN") or "").strip().lower() in {"1", "true", "yes", "on"}


async def _run_once() -> None:
    stats = await run_sync(website_user_ids=[], user_ids=[], limit=(WEBSITE_IDENTITY_SYNC_LIMIT if WEBSITE_IDENTITY_SYNC_LIMIT > 0 else None), batch_size=max(WEBSITE_IDENTITY_SYNC_BATCH_SIZE, 1), stale_minutes=max(WEBSITE_IDENTITY_SYNC_STALE_MINUTES, 0), dry_run=WEBSITE_IDENTITY_SYNC_DRY_RUN)
    log.info("website identity sync tick completed scanned=%s synced=%s missing_remote=%s failed=%s skipped=%s", stats.scanned, stats.synced, stats.missing_remote, stats.failed, stats.skipped)


async def run_forever() -> None:
    stop_event = asyncio.Event()
    interval_seconds = max(int(WEBSITE_IDENTITY_SYNC_INTERVAL_MINUTES), 1) * 60

    async def _shutdown() -> None: stop_event.set()
    loop = asyncio.get_running_loop()
    for sig_name in ("SIGINT", "SIGTERM"):
        with suppress(AttributeError, NotImplementedError): loop.add_signal_handler(getattr(signal, sig_name), lambda: asyncio.create_task(_shutdown()))

    try:
        while not stop_event.is_set():
            try: await _run_once()
            except Exception: log.exception("website identity sync tick failed")

            if stop_event.is_set(): break

            try: await asyncio.wait_for(stop_event.wait(), timeout=interval_seconds)
            except TimeoutError: continue
    finally: await bitrix_sync_api_client.aclose()


if __name__ == "__main__":
    setup_logging()
    asyncio.run(run_forever())
