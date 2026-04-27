import asyncio
import gzip
import json
from pathlib import Path

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import Message

BOT_TOKEN = "8496287141:AAEDaHGQTjhvpTQ9dMMcOhhV-sdzp_-qNHU"

SAVE_DIR = Path("stickers")
SAVE_DIR.mkdir(exist_ok=True)

bot = Bot(BOT_TOKEN)
dp = Dispatcher()


def tgs_to_json_bytes(tgs_bytes: bytes) -> bytes:
    return gzip.decompress(tgs_bytes)


async def download_tgs(file_id: str, unique_id: str) -> Path:
    file = await bot.get_file(file_id)
    out = SAVE_DIR / f"{unique_id}.tgs"
    await bot.download_file(file.file_path, destination=out)
    return out


def unpack_tgs_to_json(tgs_path: Path) -> Path:
    json_path = tgs_path.with_suffix(".json")
    json_bytes = tgs_to_json_bytes(tgs_path.read_bytes())
    parsed = json.loads(json_bytes.decode("utf-8"))
    json_path.write_text(json.dumps(parsed, ensure_ascii=False, indent=2), encoding="utf-8")
    return json_path


@dp.message(Command("start"))
async def start(message: Message):
    await message.answer("Send an animated sticker, or use /pack <sticker_set_name>")


@dp.message(Command("pack"))
async def download_pack(message: Message):
    parts = (message.text or "").split(maxsplit=1)
    if len(parts) < 2:
        await message.answer("Usage: /pack <sticker_set_name>")
        return

    set_name = parts[1].strip()
    sticker_set = await bot.get_sticker_set(set_name)

    count = 0
    for sticker in sticker_set.stickers:
        if not sticker.is_animated:
            continue
        tgs_path = await download_tgs(sticker.file_id, sticker.file_unique_id)
        unpack_tgs_to_json(tgs_path)
        count += 1

    await message.answer(f"Done. Saved {count} animated stickers from {set_name}")


@dp.message(F.sticker)
async def save_sticker(message: Message):
    sticker = message.sticker
    if not sticker.is_animated:
        await message.answer("Send an animated sticker")
        return

    tgs_path = await download_tgs(sticker.file_id, sticker.file_unique_id)
    json_path = unpack_tgs_to_json(tgs_path)
    await message.answer(f"Saved {tgs_path.name} and {json_path.name}")


async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())