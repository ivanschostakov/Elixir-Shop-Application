import asyncio
import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from src.database import SessionLocal
from src.integrations.website_reviews import sync_reviews_with_website


async def main() -> None:
    async with SessionLocal() as db:
        stats = await sync_reviews_with_website(db)
    print(stats.as_dict())


if __name__ == "__main__":
    asyncio.run(main())
