import argparse
import asyncio
import sys
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path: sys.path.insert(0, str(ROOT_DIR))

from sqlalchemy import or_, select
from sqlalchemy.orm import selectinload

from config import ufa_now
from src.app.services.website_identities.sync import refresh_linked_website_identity
from src.database import SessionLocal
from src.database.models import WebsiteIdentity, WebsiteSyncEvent
from src.integrations.bitrix import BitrixSyncApiError, get_bitrix_sync_api_client

SYNC_EVENT_TYPE = "website_identity_refresh"
bitrix_sync_api_client = get_bitrix_sync_api_client()


@dataclass(frozen=True)
class SyncStats:
    scanned: int = 0
    synced: int = 0
    missing_remote: int = 0
    failed: int = 0
    skipped: int = 0


def _parse_csv_ints(value: str | None) -> list[int]:
    if not value: return []
    parsed: list[int] = []
    for item in value.split(","):
        normalized = item.strip()
        if not normalized: continue
        try: current = int(normalized)
        except ValueError: raise argparse.ArgumentTypeError(f"Invalid integer value: {normalized}") from None
        if current > 0: parsed.append(current)
    return parsed


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Sync linked website website_identity from the Bitrix sync API into the local database.")
    parser.add_argument("--website-user-ids", type=_parse_csv_ints, default=[], help="Comma-separated website user ids to sync")
    parser.add_argument("--user-ids", type=_parse_csv_ints, default=[], help="Comma-separated local user ids to sync")
    parser.add_argument("--limit", type=int, default=None, help="Maximum number of linked website_identity to sync")
    parser.add_argument("--batch-size", type=int, default=50, help="Number of website website_identity to fetch per remote batch")
    parser.add_argument("--stale-minutes", type=int, default=None, help="Only sync website_identity older than this many minutes")
    parser.add_argument("--dry-run", action="store_true", help="Fetch remote data and report what would be synced without writing local changes")
    return parser


async def _load_target_identities(*, website_user_ids: list[int], user_ids: list[int], limit: int | None, stale_minutes: int | None) -> list[WebsiteIdentity]:
    async with SessionLocal() as session:
        stmt = select(WebsiteIdentity).options(selectinload(WebsiteIdentity.user)).order_by(WebsiteIdentity.id.asc())
        if website_user_ids: stmt = stmt.where(WebsiteIdentity.website_user_id.in_(website_user_ids))
        if user_ids: stmt = stmt.where(WebsiteIdentity.user_id.in_(user_ids))
        if stale_minutes is not None:
            cutoff = ufa_now() - timedelta(minutes=stale_minutes)
            stmt = stmt.where(or_(WebsiteIdentity.last_synced_at.is_(None), WebsiteIdentity.last_synced_at < cutoff))
        if limit is not None and limit > 0: stmt = stmt.limit(limit)
        return list((await session.execute(stmt)).scalars().all())


def _chunked(items: list[WebsiteIdentity], batch_size: int) -> list[list[WebsiteIdentity]]:
    size = max(batch_size, 1)
    return [items[index : index + size] for index in range(0, len(items), size)]


def _build_sync_event(*, website_identity: WebsiteIdentity, status: str, request_payload: dict, response_payload: dict | None = None, error_message: str | None = None) -> WebsiteSyncEvent:
    return WebsiteSyncEvent(
        user_id=website_identity.user_id,
        website_identity_id=website_identity.id,
        event_type=SYNC_EVENT_TYPE,
        request_payload=request_payload,
        response_payload=response_payload,
        status=status,
        error_message=(error_message or "")[:500] or None,
        processed_at=ufa_now(),
    )


async def _sync_identity_batch(batch: list[WebsiteIdentity], *, dry_run: bool) -> SyncStats:
    source_name = "bitrix_sync_api"
    request_payload = {"source": source_name, "website_user_ids": [identity.website_user_id for identity in batch], "dry_run": dry_run}

    try: batch_result = await bitrix_sync_api_client.fetch_snapshots(request_payload["website_user_ids"])
    except BitrixSyncApiError as exc:
        if not dry_run:
            async with SessionLocal() as session:
                for identity in batch:
                    session.add(
                        _build_sync_event(
                            website_identity=identity,
                            status="failed",
                            request_payload={"source": source_name, "website_user_id": identity.website_user_id, "dry_run": dry_run},
                            error_message=str(exc),
                        )
                    )
                await session.commit()
        return SyncStats(scanned=len(batch), failed=len(batch))

    stats = SyncStats(scanned=len(batch))
    async with SessionLocal() as session:
        wrote_pending_events = False
        for identity in batch:
            payload = batch_result.snapshots.get(identity.website_user_id)
            remote_error = batch_result.errors.get(identity.website_user_id)
            event_request_payload = {"source": source_name, "website_user_id": identity.website_user_id, "dry_run": dry_run}

            if payload is None:
                stats = SyncStats(
                    scanned=stats.scanned,
                    synced=stats.synced,
                    missing_remote=stats.missing_remote + 1,
                    failed=stats.failed,
                    skipped=stats.skipped,
                )
                if not dry_run:
                    tracked_identity = await session.get(WebsiteIdentity, identity.id)
                    if tracked_identity is not None: tracked_identity.last_synced_at = ufa_now()
                    session.add(
                        _build_sync_event(
                            website_identity=identity,
                            status="missing_remote",
                            request_payload=event_request_payload,
                            error_message=remote_error or "Bitrix sync API did not return a snapshot for this user",
                        )
                    )
                    wrote_pending_events = True
                continue

            if dry_run:
                stats = SyncStats(
                    scanned=stats.scanned,
                    synced=stats.synced,
                    missing_remote=stats.missing_remote,
                    failed=stats.failed,
                    skipped=stats.skipped + 1,
                )
                continue

            try: refreshed_identity = await refresh_linked_website_identity(session, website_identity=identity, payload=payload)
            except Exception as exc:
                await session.rollback()
                stats = SyncStats(
                    scanned=stats.scanned,
                    synced=stats.synced,
                    missing_remote=stats.missing_remote,
                    failed=stats.failed + 1,
                    skipped=stats.skipped,
                )
                session.add(_build_sync_event(website_identity=identity, status="failed", request_payload=event_request_payload, error_message=str(exc)))
                await session.commit()
                wrote_pending_events = False
                continue

            stats = SyncStats(
                scanned=stats.scanned,
                synced=stats.synced + 1,
                missing_remote=stats.missing_remote,
                failed=stats.failed,
                skipped=stats.skipped,
            )
            session.add(
                _build_sync_event(
                    website_identity=refreshed_identity,
                    status="synced",
                    request_payload=event_request_payload,
                    response_payload={
                        "website_user_id": refreshed_identity.website_user_id,
                        "coupon_count": len(refreshed_identity.coupon_snapshots),
                        "discount_group_count": len(refreshed_identity.discount_entitlements),
                        "has_bonus_account": refreshed_identity.bonus_account_snapshot is not None,
                        "last_synced_at": refreshed_identity.last_synced_at.isoformat() if refreshed_identity.last_synced_at else None,
                    },
                )
            )
            await session.commit()
            wrote_pending_events = False

        if not dry_run and wrote_pending_events: await session.commit()

    return stats


async def run_sync(*, website_user_ids: list[int], user_ids: list[int], limit: int | None, batch_size: int, stale_minutes: int | None, dry_run: bool) -> SyncStats:
    if not bitrix_sync_api_client.is_configured(): raise BitrixSyncApiError("Website identity sync is not configured. Set BITRIX_SYNC_API_ENDPOINT, BITRIX_SYNC_API_APP_KEY, and BITRIX_SYNC_API_APP_SECRET.")
    identities = await _load_target_identities(website_user_ids=website_user_ids, user_ids=user_ids, limit=limit, stale_minutes=stale_minutes)
    total = SyncStats()
    for batch in _chunked(identities, batch_size):
        batch_stats = await _sync_identity_batch(batch, dry_run=dry_run)
        total = SyncStats(
            scanned=total.scanned + batch_stats.scanned,
            synced=total.synced + batch_stats.synced,
            missing_remote=total.missing_remote + batch_stats.missing_remote,
            failed=total.failed + batch_stats.failed,
            skipped=total.skipped + batch_stats.skipped,
        )
    return total


async def _async_main() -> int:
    args = _build_arg_parser().parse_args()
    try:
        stats = await run_sync(
            website_user_ids=args.website_user_ids,
            user_ids=args.user_ids,
            limit=args.limit,
            batch_size=args.batch_size,
            stale_minutes=args.stale_minutes,
            dry_run=args.dry_run,
        )
        print(f"website_identity_sync scanned={stats.scanned} synced={stats.synced} missing_remote={stats.missing_remote} failed={stats.failed} skipped={stats.skipped}")
        return 0 if stats.failed == 0 else 1
    finally:
        await bitrix_sync_api_client.aclose()


def main() -> None: raise SystemExit(asyncio.run(_async_main()))


if __name__ == "__main__":
    main()
