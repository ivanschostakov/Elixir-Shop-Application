import asyncio
import json
import logging
import signal
from contextlib import suppress

from config import ADMIN_JOB_QUEUE_NAME
from logger import setup_logging
from src.app.modules.admin.integrations import _run_moysklad_catalog_sync
from src.app.services.cache import get_cache_service

log = logging.getLogger("worker.admin_jobs")


async def _handle_job(raw_payload: str) -> None:
    try:
        payload = json.loads(raw_payload)
        job_type = payload["type"]
        run_id = int(payload["run_id"])
    except (KeyError, TypeError, ValueError, json.JSONDecodeError):
        log.error("Discarding invalid admin job payload")
        return

    if job_type == "moysklad_catalog_sync":
        await _run_moysklad_catalog_sync(run_id)
        return
    log.error("Discarding unsupported admin job type=%s run_id=%s", job_type, run_id)


async def run_forever() -> None:
    stop_event = asyncio.Event()
    cache = get_cache_service()
    await cache.connect()
    redis = cache.client
    if redis is None:
        raise RuntimeError("Redis is required for the admin job worker")

    loop = asyncio.get_running_loop()
    for signal_name in ("SIGINT", "SIGTERM"):
        with suppress(AttributeError, NotImplementedError):
            loop.add_signal_handler(getattr(signal, signal_name), stop_event.set)

    try:
        while not stop_event.is_set():
            item = await redis.blpop(ADMIN_JOB_QUEUE_NAME, timeout=5)
            if item is None:
                continue
            _, payload = item
            try:
                await _handle_job(payload)
            except Exception:
                log.exception("Admin background job failed")
    finally:
        await cache.close()


if __name__ == "__main__":
    setup_logging()
    asyncio.run(run_forever())
