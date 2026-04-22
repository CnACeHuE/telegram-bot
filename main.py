import logging
from aiogram import Bot, Dispatcher, executor, types
import config
from database import db
from modules.clans import clan_router  # Мы создадим это в папке modules

logging.basicConfig(level=logging.INFO)
bot = Bot(token=config.API_TOKEN, parse_mode="HTML")
dp = Dispatcher(bot)

# Регистрация команд кланов
@dp.message_handler(lambda m: m.text and m.text.lower().startswith(('создать пантеон', 'пантеон', 'призвать')))
async def clans_handler(m: types.Message):
    await clan_router(m)

# Глобальный обработчик (Опыт)
@dp.message_handler(content_types=['text'])
async def global_handler(m: types.Message):
    # Здесь твоя логика check_user и начисления msg_count
    pass

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
    
