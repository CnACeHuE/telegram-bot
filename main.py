import logging
from aiogram import Bot, Dispatcher, executor, types
import config
from database import db
from modules.clans import clan_router # Импорт твоих кланов

logging.basicConfig(level=logging.INFO)
bot = Bot(token=config.API_TOKEN, parse_mode="HTML")
dp = Dispatcher(bot)

# --- ВСПОМОГАТЕЛЬНАЯ ФУНКЦИЯ (Важно!) ---
def check_user(u: types.User):
    name = u.first_name.replace("<", "&lt;").replace(">", "&gt;")
    db.execute("INSERT INTO users (user_id, username) VALUES (?, ?) ON CONFLICT (user_id) DO UPDATE SET username = ?", (u.id, name, name))

# --- ОБРАБОТЧИК КЛАНОВ ---
@dp.message_handler(lambda m: m.text and m.text.lower().split()[0] in ['создать', 'пантеон', 'клан', 'призвать', 'внести'])
async def handle_clans(m: types.Message):
    check_user(m.from_user)
    await clan_router(m)

# --- ОБРАБОТЧИК ИНФО (Ми / Профиль) ---
@dp.message_handler(lambda m: m.text and m.text.lower().split()[0] in ['ми', 'профиль', 'ю*'])
async def info_cmd(m: types.Message):
    check_user(m.from_user)
    t = m.reply_to_message.from_user if m.reply_to_message else m.from_user
    u = db.execute("SELECT power_points, msg_count, admin_rank, clan_role FROM users WHERE user_id = ?", (t.id,))
    
    res = f"✨ <b>СВИТОК ОБИТЕЛИ</b>\n━━━━━━━━━━━━━━\n"
    res += f"👤 <b>Имя:</b> {t.first_name}\n"
    res += f"🎖 <b>Ранг:</b> {config.ADM_RANKS.get(u[2], 'Участник')}\n"
    res += f"🔱 <b>В пантеоне:</b> {u[3]}\n"
    res += f"⚡️ <b>Мощь:</b> <code>{u[0]}</code> 💠\n"
    res += f"📜 <b>Опыт:</b> <code>{u[1]}</code>\n━━━━━━━━━━━━━━"
    await m.answer(res)

# --- ГЛОБАЛЬНЫЙ СЧЕТЧИК СООБЩЕНИЙ ---
@dp.message_handler(content_types=['text'])
async def global_handler(m: types.Message):
    check_user(m.from_user)
    # Начисляем опыт
    db.execute("UPDATE users SET msg_count = msg_count + 1 WHERE user_id = ?", (m.from_user.id,))

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
    
