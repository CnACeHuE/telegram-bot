
import logging
from aiogram import Bot, Dispatcher, executor, types
import config, handlers
from database import db

logging.basicConfig(level=logging.INFO)
bot = Bot(token=config.API_TOKEN, parse_mode="HTML")
dp = Dispatcher(bot)

# 1. Справка
@dp.message_handler(commands=['help', 'start'])
@dp.message_handler(lambda m: m.text and m.text.lower() == 'помощь')
async def h_help(m: types.Message):
    await m.answer("📖 <b>СПРАВОЧНИК</b>\n<code>Ми</code>, <code>Профиль</code>, <code>Сильнейшие</code>, <code>Активчики</code>\n<code>Кара</code>, <code>Гив</code>, <code>.сбор</code>")

# 2. Профиль
@dp.message_handler(lambda m: m.text and m.text.lower() in ['ми', 'профиль', 'ю*'])
async def h_profile(m: types.Message): await handlers.cmd_profile(m)

# 3. Топы
@dp.message_handler(lambda m: m.text and m.text.lower() in ['сильнейшие', 'активчики'])
async def h_tops(m: types.Message): await handlers.cmd_tops(m)

# 4. Админка
@dp.message_handler(lambda m: m.text and m.text.lower().startswith(('.пд', 'гив', 'кара', '.сбор')))
async def h_admin(m: types.Message): await handlers.cmd_admin(m)

# 5. Глобальный счетчик опыта (СТРОГО ПОСЛЕДНИЙ)
@dp.message_handler(content_types=['text'])
async def h_xp(m: types.Message):
    db.execute("INSERT INTO users (user_id, username, msg_count, power_points) VALUES (%s, %s, 1, 100) "
               "ON CONFLICT (user_id) DO UPDATE SET msg_count = users.msg_count + 1, username = EXCLUDED.username", 
               (m.from_user.id, m.from_user.first_name))

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
    
