import asyncio
import json

from logger import setup_logging
from src.integrations.moysklad import run_moysklad_initial_relink


async def _main() -> None:
    stats = await run_moysklad_initial_relink()
    print(json.dumps(stats.as_dict(), ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    setup_logging()
    asyncio.run(_main())
