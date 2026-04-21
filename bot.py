import asyncio
import os
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command

API_TOKEN = os.getenv("API_TOKEN")

bot = Bot(token=API_TOKEN)
dp = Dispatcher()

@dp.message(Command("start"))
async def start(message: types.Message):
    await message.answer("Бот работает 🚀")

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
