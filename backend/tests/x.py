

from aiogram import Bot, Dispatcher, types

bot = Bot(token="")

dp = Dispatcher()

@dp.message()
async def echo(message: types.Message):
    message.topic
