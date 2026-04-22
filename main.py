import logging, random
from aiogram import Bot, Dispatcher, types
from aiogram.utils import executor
import config
from database import db

logging.basicConfig(level=logging.INFO)
bot = Bot(token=config.API_TOKEN, parse_mode="HTML")
dp = Dispatcher(bot)

# Красивый хелп из твоего примера
HELP_TEXT = """📖 <b>БИБЛИОТЕКА</b>
━━━━━━━━━━━━━━
🎮 <b>Игры:</b>
— лотерея / пвп / *передать
— ми / профиль / ю*

🛠 <b>Админ:</b>
— сильнейшие / активчики
— кара [реплей] / гив [реплей]

👑 <b>Создатель:</b>
— эволюция / .пд / .сбор
━━━━━━━━━━━━━━"""

@dp.message_handler(commands=['start', 'help'])
async def send_help(m: types.Message):
    await m.answer(HELP_TEXT)

# Команда МИ / Профиль / Ю*
@dp.message_handler(lambda m: m.text and m.text.lower() in ['ми', 'профиль', 'ю*'])
async def profile(m: types.Message):
    user = db.execute("SELECT power_points, msg_count, admin_rank FROM users WHERE user_id = %s", (m.from_user.id,))
    if not user: return
    
    await m.answer(
        f"👤 <b>{m.from_user.first_name}</b>\n"
        f"💠 Очки силы: {user[0]}\n"
        f"📈 Активность: {user[1]} сообщ.\n"
        f"🛡 Ранг: {config.ADM_RANKS.get(user[2], 'Участник')}"
    )

# Команды Сильнейшие и Активчики
@dp.message_handler(lambda m: m.text and m.text.lower() in ['сильнейшие', 'активчики'])
async def top_players(m: types.Message):
    order = "power_points" if "сильнейшие" in m.text.lower() else "msg_count"
    tops = db.fetchall(f"SELECT username, {order} FROM users ORDER BY {order} DESC LIMIT 10")
    
    res = "🏆 <b>ТОП ИГРОКОВ:</b>\n\n"
    for i, row in enumerate(tops, 1):
        res += f"{i}. {row[0] or 'Аноним'} — {row[1]}\n"
    await m.answer(res)

# Обработка кланов (вызов из модуля)
@dp.message_handler(lambda m: m.text and m.text.lower().split()[0] in ['клан', 'пантеон'])
async def handle_clans(m: types.Message):
    from modules.clans import clan_router
    await clan_router(m)

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
    
