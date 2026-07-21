import asyncio

from logger import setup_logging
from src.integrations.telegram.userbot import sync_telegram_forum_topics


async def main() -> None:
    result = await sync_telegram_forum_topics()
    print(
        "Telegram topics synchronized "
        f"total={result.total} discovered={result.discovered} updated={result.updated} "
        f"restored={result.restored} deleted={result.deleted}"
    )


if __name__ == "__main__":
    setup_logging()
    asyncio.run(main())
