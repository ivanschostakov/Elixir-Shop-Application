import asyncio
import gzip
import logging
import os

from pathlib import Path

from aiogram import Bot, Dispatcher, F
from aiogram.exceptions import TelegramAPIError, TelegramNetworkError
from aiogram.types import Message, FSInputFile

DOWNLOAD_DIR = Path("downloads")
DOWNLOAD_DIR.mkdir(exist_ok=True)

LOGGER = logging.getLogger(__name__)
TOKEN_ENV_VAR = "TELEGRAM_BOT_TOKEN"

token = os.getenv(TOKEN_ENV_VAR)
if not token:
    raise RuntimeError(
        f"Missing Telegram bot token. Set {TOKEN_ENV_VAR} in your environment and run again."
    )

bot = Bot(token=token)
dp = Dispatcher()


@dp.message(F.text == "/start")
async def start_handler(message: Message):
    await message.answer("Send me an animated Telegram sticker, and I will return it as Lottie JSON.")


@dp.message(F.sticker)
async def sticker_handler(message: Message):
    sticker = message.sticker

    if not sticker.is_animated:
        await message.answer("This is not an animated Lottie sticker. Send a .tgs animated sticker.")
        return

    tgs_path = DOWNLOAD_DIR / f"{sticker.file_unique_id}.tgs"
    json_path = DOWNLOAD_DIR / f"{sticker.file_unique_id}.json"

    tg_file = await bot.get_file(sticker.file_id)
    await bot.download_file(tg_file.file_path, destination=tgs_path)

    with gzip.open(tgs_path, "rb") as f_in:
        json_data = f_in.read()

    json_path.write_bytes(json_data)

    await message.answer_document(
        document=FSInputFile(json_path),
        caption="Here is the sticker converted to Lottie JSON.",
    )


@dp.message()
async def fallback_handler(message: Message):
    await message.answer("Send me an animated Telegram sticker.")


async def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    LOGGER.info("Checking Telegram connectivity...")
    try:
        me = await bot.get_me()
    except TelegramNetworkError as exc:
        raise RuntimeError(
            "Could not reach Telegram API. Check internet/DNS access and try again."
        ) from exc
    except TelegramAPIError as exc:
        raise RuntimeError(
            "Telegram API rejected the token or request. Check TELEGRAM_BOT_TOKEN."
        ) from exc

    LOGGER.info("Bot is online as @%s (id=%s)", me.username, me.id)
    LOGGER.info("Polling started. Send /start to the bot. Press Ctrl+C to stop.")
    try:
        await dp.start_polling(bot)
    finally:
        LOGGER.info("Polling stopped.")
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
