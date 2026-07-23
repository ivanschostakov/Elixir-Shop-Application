import asyncio
import logging
import signal

from contextlib import suppress

from config import (
    ADMIN_JOB_QUEUE_NAME,
    ADMIN_JOB_RECOVERY_INTERVAL_SECONDS,
    CUSTOMER_EVENT_CLEANUP_INTERVAL_SECONDS,
    CUSTOMER_EVENT_RETENTION_DAYS,
)
from logger import setup_logging
from src.app.services.admin.jobs import (
    PROCESSING_QUEUE_NAME,
    acknowledge_queued_marker,
    execute_integration_run,
    move_due_scheduled_runs,
    parse_job,
    recover_due_database_runs,
    recover_processing_queue,
    record_worker_heartbeat,
)
from src.app.services.cache import get_cache_service
from src.app.services.customer_intelligence import delete_expired_customer_events
from src.database import SessionLocal

log = logging.getLogger("worker.admin_jobs")


async def _handle_job(raw_payload: str) -> None:
    run_id = parse_job(raw_payload)
    if run_id is None:
        log.error("Discarding invalid admin job payload")
        return
    await acknowledge_queued_marker(run_id)
    await execute_integration_run(run_id)


async def _cleanup_customer_events() -> int:
    async with SessionLocal() as db:
        deleted = await delete_expired_customer_events(
            db,
            retention_days=CUSTOMER_EVENT_RETENTION_DAYS,
        )
    if deleted:
        log.info("Deleted %s expired customer events", deleted)
    return deleted


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

    await recover_processing_queue()
    await recover_due_database_runs()
    await _cleanup_customer_events()
    last_recovery_at = loop.time()
    last_event_cleanup_at = loop.time()
    try:
        while not stop_event.is_set():
            await record_worker_heartbeat("admin_jobs")
            await move_due_scheduled_runs()
            if loop.time() - last_recovery_at >= max(5, ADMIN_JOB_RECOVERY_INTERVAL_SECONDS):
                await recover_due_database_runs()
                last_recovery_at = loop.time()
            if loop.time() - last_event_cleanup_at >= max(300, CUSTOMER_EVENT_CLEANUP_INTERVAL_SECONDS):
                await _cleanup_customer_events()
                last_event_cleanup_at = loop.time()

            payload = await redis.brpoplpush(ADMIN_JOB_QUEUE_NAME, PROCESSING_QUEUE_NAME, timeout=5)
            if payload is None:
                continue
            try:
                await _handle_job(payload)
            except Exception:
                log.exception("Admin background job failed")
            finally:
                await redis.lrem(PROCESSING_QUEUE_NAME, 1, payload)
    finally:
        await cache.close()


if __name__ == "__main__":
    setup_logging()
    asyncio.run(run_forever())
