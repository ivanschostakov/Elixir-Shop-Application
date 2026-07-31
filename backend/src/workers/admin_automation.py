import asyncio
import logging
import signal

from contextlib import suppress

from config import ADMIN_AUTOMATION_INTERVAL_SECONDS
from logger import setup_logging
from src.app.services.admin.automation import process_order_automations_once
from src.app.services.admin.jobs import record_worker_heartbeat
from src.app.services.admin.sla import scan_sla_breaches
from src.app.services.referrals.paid_orders import (
    backfill_missing_paid_order_rewards,
    finalize_closed_app_referral_accruals,
    retry_unsynced_app_referral_purchases,
)
from src.app.services.referrals.wallet_sync import (
    sync_approved_referral_accruals_to_bonus_wallet,
)
from src.database import get_session


log = logging.getLogger("worker.admin_automation")


async def _run_once() -> None:
    await record_worker_heartbeat("admin_automation")
    results = await process_order_automations_once()
    async with get_session() as session:
        sla_breaches = await scan_sla_breaches(session)
        referral_purchase_backfill = await backfill_missing_paid_order_rewards(session)
        referral_purchase_sync = await retry_unsynced_app_referral_purchases(session)
        referral_accruals = await finalize_closed_app_referral_accruals(session)
        referral_wallet_sync = (
            await sync_approved_referral_accruals_to_bonus_wallet(session)
        )
    if (
        results["executed"]
        or results["failed"]
        or sla_breaches
        or referral_purchase_backfill["processed"]
        or referral_purchase_sync["processed"]
        or referral_accruals["processed"]
        or referral_accruals["failed"]
        or referral_wallet_sync["processed"]
        or referral_wallet_sync["failed"]
    ):
        log.info(
            "automation tick completed rules=%s sla_breaches=%s referral_purchase_backfill=%s referral_purchase_sync=%s referral_accruals=%s referral_wallet_sync=%s",
            results,
            sla_breaches,
            referral_purchase_backfill,
            referral_purchase_sync,
            referral_accruals,
            referral_wallet_sync,
        )


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
