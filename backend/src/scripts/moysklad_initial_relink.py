import asyncio
import argparse
import json

from logger import setup_logging
from src.integrations.moysklad import run_moysklad_initial_relink


async def _main() -> None:
    parser = argparse.ArgumentParser(description="Relink local catalog system IDs from legacy 1C IDs to MoySklad IDs.")
    parser.add_argument("--dry-run", action="store_true", help="Fetch and report planned changes without touching DB or images.")
    args = parser.parse_args()

    stats = await run_moysklad_initial_relink(dry_run=args.dry_run)
    print(json.dumps(stats.as_dict(), ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    setup_logging()
    asyncio.run(_main())
