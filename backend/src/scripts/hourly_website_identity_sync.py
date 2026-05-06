import argparse
import asyncio
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path: sys.path.insert(0, str(ROOT_DIR))

from src.scripts.sync_website_identities_from_bitrix_vm import run_sync

DEFAULT_STALE_MINUTES = 23 * 60
DEFAULT_BATCH_SIZE = 50


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Daily task for syncing stale linked website identity snapshots.")
    parser.add_argument(
        "--stale-minutes",
        type=int,
        default=DEFAULT_STALE_MINUTES,
        help=f"Only sync website_identity older than this many minutes (default: {DEFAULT_STALE_MINUTES})",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=DEFAULT_BATCH_SIZE,
        help=f"Number of website website_identity to fetch per remote batch (default: {DEFAULT_BATCH_SIZE})",
    )
    parser.add_argument("--limit", type=int, default=None, help="Maximum number of linked website_identity to sync")
    parser.add_argument(
        "--dry-run", action="store_true", help="Fetch remote data and report what would be synced without writing local changes"
    )
    return parser


async def _async_main() -> int:
    args = _build_arg_parser().parse_args()
    stats = await run_sync(
        website_user_ids=[],
        user_ids=[],
        limit=args.limit,
        batch_size=args.batch_size,
        stale_minutes=args.stale_minutes,
        dry_run=args.dry_run,
    )
    print(
        "website_identity_hourly_sync "
        f"scanned={stats.scanned} synced={stats.synced} missing_remote={stats.missing_remote} "
        f"failed={stats.failed} skipped={stats.skipped} "
        f"stale_minutes={args.stale_minutes} batch_size={args.batch_size}"
    )
    return 0 if stats.failed == 0 else 1


def main() -> None:
    raise SystemExit(asyncio.run(_async_main()))


if __name__ == "__main__":
    main()
