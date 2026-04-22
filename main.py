import logging, random
from aiogram import Bot, Dispatcher, types
from aiogram.utils import executor
import config
from database import db
from modules.clans import clan_router

logging.basicConfig(level=logging.INFO)
bot = Bot(token=config.API_TOKEN, parse_mode="HTML")
dp = Dispatcher(bot)

# --- ФУНКЦИИ РАНГОВ И ОФОРМЛЕНИЯ ---
def get_rank(msgs):
    if msgs >= 10000: return "Лорд 👑"
    if msgs >= 5000: return "Золотая черепаха 🐢"
    if msgs >= 3000: return "Синий бафф 🟦"
    if msgs >= 2000: return "Красный бафф 🟥"
    if msgs >= 1500: return "Динозаврик 🦖"
    if msgs >= 1000: return "Жук 🪲"
    if msgs >= 600: return "Лесной медведь 🐻"
    if msgs >= 300: return "Краб 🦀"
    return "Вазон 🌱"

def get_mention(user_id, name):
    return f'<a href="tg://user?id={user_id}">{name}</a>'

# --- КОМАНДА МИ / Ю* (ИСПРАВЛЕНО) ---
@dp.message_handler(lambda m: m.text and m.text.lower() in ['ми', 'профиль', 'ю*'])
async def profile(m: types.Message):
    # Если это ответ на сообщение — смотрим профиль того человека, если нет — свой
    target = m.reply_to_message.from_user if m.reply_to_message else m.from_user
    
    user = db.execute("SELECT power_points, msg_count, admin_rank, clan_role FROM users WHERE user_id = %s", (target.id,))
    if not user:
        # Если пользователя нет в базе (например, при ю* на нового человека), добавим его
        db.execute("INSERT INTO users (user_id, username) VALUES (%s, %s)", (target.id, target.first_name))
        user = (100, 0, 0, None)

    rank = get_rank(user[1])
    adm_status = "БОЖЕСТВО 🔱" if user[2] >= 3 else "Житель"
    
    ui = (f"✨ <b>СВИТОК ОБИТЕЛИ</b>\n"
          f"━━━━━━━━━━━━━━\n"
          f"👤 <b>Имя:</b> {get_mention(target.id, target.first_name)}\n"
          f"🎖 <b>Эв. статус:</b> <i>{rank}</i>\n"
          f"🔱 <b>Ранг:</b> {adm_status}\n"
          f"⚡️ <b>Мощь:</b> <code>{user[0]}</code> 💠\n"
          f"📜 <b>Опыт:</b> <code>{user[1]}</code>\n"
          f"━━━━━━━━━━━━━━")
    await m.answer(ui)

# --- АДМИН-КОМАНДЫ (ГИВ / КАРА) ---
@dp.message_handler(lambda m: m.text and m.text.lower().startswith(('гив', 'кара')))
async def admin_cmds(m: types.Message):
    # Проверка на админа (OWNER_ID или ранг в базе)
    self_adm = db.execute("SELECT admin_rank FROM users WHERE user_id = %s", (m.from_user.id,))
    if m.from_user.id != config.OWNER_ID and (not self_adm or self_adm[0] < 3):
        return

    if not m.reply_to_message:
        return await m.reply("<b>⚠️ Ответь на сообщение цели!</b>")

    args = m.text.split()
    target_id = m.reply_to_message.from_user.id
    
    if args[0].lower() == 'гив':
        try:
            amt = int(args[1])
            db.execute("UPDATE users SET power_points = power_points + %s WHERE user_id = %s", (amt, target_id))
            await m.answer(f"🔱 {get_mention(target_id, m.reply_to_message.from_user.first_name)} получил <code>{amt}</code> 💠")
        except: pass

    elif args[0].lower() == 'кара':
        if target_id == config.OWNER_ID:
            return await m.answer("🛡 Кара бессильна против Создателя.")
        
        db.execute("UPDATE users SET power_points = 0 WHERE user_id = %s", (target_id,))
        await m.answer(f"⚡️ <b>НЕБЕСНАЯ КАРА!</b> Мощь игрока {get_mention(target_id, m.reply_to_message.from_user.first_name)} обнулена.")

# --- СЧЕТЧИК СООБЩЕНИЙ (ДЛЯ ЭВОЛЮЦИИ) ---
@dp.message_handler(content_types=['text'])
async def message_counter(m: types.Message):
    # Регистрация/обновление пользователя
    name = m.from_user.first_name.replace("<", "").replace(">", "")
    db.execute(
        "INSERT INTO users (user_id, username, msg_count) VALUES (%s, %s, 1) "
        "ON CONFLICT (user_id) DO UPDATE SET msg_count = users.msg_count + 1, username = %s",
        (m.from_user.id, name, name)
    )
    
    # Если это команда клана — передаем в роутер
    if m.text and m.text.lower().split()[0] in ['клан', 'пантеон', 'создать']:
        await clan_router(m)

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
        
