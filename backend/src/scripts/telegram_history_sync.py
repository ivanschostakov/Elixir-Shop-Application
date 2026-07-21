import asyncio

from logger import setup_logging
from src.integrations.telegram.userbot import sync_telegram_forum_history


async def main() -> None:
    result = await sync_telegram_forum_history()
    print(f"Telegram history synchronized {result}")


if __name__ == "__main__":
    setup_logging()
    asyncio.run(main())
