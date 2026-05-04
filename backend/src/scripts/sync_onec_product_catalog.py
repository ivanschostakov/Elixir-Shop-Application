import asyncio
import sys

from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from src.integrations.moysklad import sync_moysklad_product_catalog


async def main() -> None:
    stats = await sync_moysklad_product_catalog()
    for key, value in stats.as_dict().items():
        print(f"{key}={value}")


if __name__ == "__main__":
    asyncio.run(main())
