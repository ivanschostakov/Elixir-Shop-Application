import asyncio

from logger import setup_logging
from src.integrations.telegram.userbot import authorize_telegram_userbot


async def main() -> None:
    user_id = await authorize_telegram_userbot()
    print(f"Telegram user session authorized user_id={user_id}")


if __name__ == "__main__":
    setup_logging()
    asyncio.run(main())
