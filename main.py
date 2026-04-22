import logging, os, random
from aiogram import Bot, Dispatcher, types
from aiogram.utils import executor
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
import config # Берем токен и OWNER_ID отсюда
from database import db # Подключаемся к базе через наш новый класс
from modules.clans import clan_router # Импортируем логику из папки modules

# --- НАСТРОЙКИ ---
logging.basicConfig(level=logging.INFO)
bot = Bot(token=config.API_TOKEN, parse_mode="HTML") 
dp = Dispatcher(bot)

# --- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ---
def check_user(u: types.User):
    name = u.first_name.replace("<", "&lt;").replace(">", "&gt;")
    # Формат %s обязателен для PostgreSQL на Railway
    db.execute(
        "INSERT INTO users (user_id, username) VALUES (%s, %s) "
        "ON CONFLICT (user_id) DO UPDATE SET username = %s", 
        (u.id, name, name)
    )

def get_mention(user_id, name):
    return f'<a href="tg://user?id={user_id}">{name}</a>'

def get_rank(msgs):
    if msgs >= 10000: return "Лорд 👑"
    if msgs >= 5000: return "Золотая черепаха 🐢"
    if msgs >= 3000: return "Синий бафф 🟦"
    if msgs >= 2000: return "Красный бафф 🟥"
    if msgs >= 1500: return "Динозаврик 🦖"
    if msgs >= 1000: return "Жук 🪲"
    if msgs >= 600: return "Лесной медведь 🐻"
    if msgs >= 300: return "Краб 🦀"
    return "Вазон"

async def is_admin(user_id):
    if user_id == config.OWNER_ID: return True
    res = db.execute("SELECT admin_rank FROM users WHERE user_id = %s", (user_id,))
    return res and res[0] >= 3

# --- 1. АДМИН-ЛОГИКА ---
@dp.message_handler(lambda m: m.text and m.text.lower().startswith(('гив', 'божество+', 'божество-', 'кара')))
async def admin_tools(m: types.Message):
    if not await is_admin(m.from_user.id): return
    
    args = m.text.lower().split()
    cmd = args[0]
    target = m.reply_to_message.from_user if m.reply_to_message else m.from_user
    
    if cmd == 'божество+':
        if not m.reply_to_message: return await m.reply("<b>⚠️ Ответь на сообщение цели!</b>")
        db.execute("UPDATE users SET admin_rank = 3 WHERE user_id = %s", (target.id,))
        await m.answer(f"⚡️ {get_mention(target.id, target.first_name)} возведен в ранг <b>Божества</b>!")
    
    elif cmd == 'божество-':
        if target.id == config.OWNER_ID and m.from_user.id != config.OWNER_ID:
            return await m.answer("🪐 Лишь сам Создатель властен над своей судьбой.")
        db.execute("UPDATE users SET admin_rank = 0 WHERE user_id = %s", (target.id,))
        await m.answer(f"☁️ {get_mention(target.id, target.first_name)} теперь в ранге игрока.")
    
    elif cmd == 'кара':
        if not m.reply_to_message: return await m.reply("<b>⚠️ Ответь на сообщение грешника!</b>")
        if target.id == config.OWNER_ID: return await m.answer("🛡 Кара бессильна против Создателя.")
        try:
            amt = int(args[1]) if len(args) > 1 else None
            if amt:
                db.execute("UPDATE users SET power_points = GREATEST(0, power_points - %s) WHERE user_id = %s", (amt, target.id))
                await m.answer(f"🔥 {get_mention(target.id, target.first_name)} поражен карой на <code>{amt}</code> 💠")
            else:
                db.execute("UPDATE users SET power_points = 0 WHERE user_id = %s", (target.id,))
                await m.answer(f"⚡️ <b>НЕБЕСНАЯ КАРА!</b> Мощь {get_mention(target.id, target.first_name)} обнулена.")
        except: pass
        
    elif cmd == 'гив':
        if not m.reply_to_message: return await m.reply("<b>⚠️ Ответь на сообщение цели!</b>")
        try:
            amt = int(args[1])
            db.execute("UPDATE users SET power_points = power_points + %s WHERE user_id = %s", (amt, target.id))
            await m.answer(f"🔱 {get_mention(target.id, target.first_name)} получил <code>{amt}</code> 💠 мощи.")
        except: pass

# --- 2. ИГРОВАЯ ЛОГИКА (Лотерея и ПВП) ---
@dp.message_handler(lambda m: m.text and m.text.lower().startswith(('лотерея', 'деп', 'пвп')))
async def games(m: types.Message):
    check_user(m.from_user)
    txt = m.text.lower().split()
    
    if txt[0] in ['лотерея', 'деп']:
        try:
            bet = int(txt[1]) if len(txt) > 1 and txt[1].isdigit() else 50
            user = db.execute("SELECT power_points FROM users WHERE user_id = %s", (m.from_user.id,))
            if user[0] < bet: return await m.reply("❌ Недостаточно мощи!")
            
            mult = random.choices([0, 1, 2, 5], weights=[50, 20, 20, 10])[0]
            new_bal = user[0] - bet + (bet * mult)
            db.execute("UPDATE users SET power_points = %s WHERE user_id = %s", (new_bal, m.from_user.id))
            
            status = "🔴 ПРОИГРЫШ" if mult == 0 else f"🟢 ВЫИГРЫШ x{mult}"
            await m.answer(f"{status}\n💰 Баланс: <code>{new_bal}</code> 💠")
        except: pass

    elif txt[0] == 'пвп' and m.reply_to_message:
        bet = int(txt[1]) if len(txt) > 1 and txt[1].isdigit() else 50
        kb = InlineKeyboardMarkup().add(InlineKeyboardButton("⚔️ ПРИНЯТЬ БОЙ", callback_data=f"pvp_{m.from_user.id}_{bet}"))
        await m.answer(f"⚔️ {get_mention(m.from_user.id, m.from_user.first_name)} вызывает на бой!\nСтавка: <b>{bet}</b> 💠", reply_markup=kb)

# --- 3. ПРОФИЛЬ И ТОПЫ ---
@dp.message_handler(lambda m: m.text and m.text.lower().strip() in ['ми', 'профиль', 'ю*'])
async def cmd_profile(m: types.Message):
    t = m.reply_to_message.from_user if m.reply_to_message else m.from_user
    check_user(t)
    u = db.execute("SELECT power_points, msg_count, admin_rank, clan_role FROM users WHERE user_id = %s", (t.id,))
    role = "БОЖЕСТВО 🔱" if u[2] >= 3 else get_rank(u[1])
    
    ui = (f"✨ <b>СВИТОК ОБИТЕЛИ</b>\n━━━━━━━━━━━━━━\n"
          f"👤 <b>Имя:</b> {get_mention(t.id, t.first_name)}\n"
          f"🎖 <b>Ранг:</b> <i>{role}</i>\n"
          f"🔱 <b>Пантеон:</b> {u[3]}\n"
          f"⚡️ <b>Мощь:</b> <code>{u[0]}</code> 💠\n"
          f"📜 <b>Опыт:</b> <code>{u[1]}</code>\n━━━━━━━━━━━━━━")
    await m.answer(ui)

@dp.message_handler(lambda m: m.text and m.text.lower().startswith(('сильнейшие', 'активчики')))
async def tops(m: types.Message):
    if 'сильнейшие' in m.text.lower():
        users = db.fetchall("SELECT user_id, username, power_points FROM users ORDER BY power_points DESC LIMIT 10")
        res = "🏆 <b>СИЛЬНЕЙШИЕ БОГИ:</b>\n\n"
        for i, u in enumerate(users, 1): res += f"{i}. {get_mention(u[0], u[1])} — <code>{u[2]}</code> 💠\n"
    else:
        users = db.fetchall("SELECT user_id, username, msg_count FROM users ORDER BY msg_count DESC LIMIT 10")
        res = "🔥 <b>АКТИВЧИКИ ОБИТЕЛИ:</b>\n\n"
        for i, u in enumerate(users, 1): res += f"{i}. {get_mention(u[0], u[1])} — <code>{u[2]}</code> 📜\n"
    await m.answer(res)

# --- 4. ПЕРЕДАЧА И СВЯЗЬ С МОДУЛЯМИ ---
@dp.message_handler(lambda m: m.text and m.text.lower().startswith(('*передать', 'создать', 'пантеон', 'клан', 'призвать', 'внести')))
async def handle_external(m: types.Message):
    check_user(m.from_user)
    if m.text.lower().startswith('*передать') and m.reply_to_message:
        try:
            amt = int(m.text.split()[1])
            tid = m.reply_to_message.from_user.id
            db.execute("UPDATE users SET power_points = power_points - %s WHERE user_id = %s", (amt, m.from_user.id))
            db.execute("UPDATE users SET power_points = power_points + %s WHERE user_id = %s", (amt, tid))
            await m.answer(f"🤝 Передано <code>{amt}</code> 💠")
        except: pass
    else:
        # Отправляем команду в файл modules/clans.py
        await clan_router(m)

@dp.callback_query_handler(lambda c: c.data.startswith('pvp_'))
async def pvp_callback(c: types.CallbackQuery):
    _, ch_id, bet = c.data.split('_')
    ch_id, bet = int(ch_id), int(bet)
    if c.from_user.id == ch_id: return
    
    b1 = db.execute("SELECT power_points FROM users WHERE user_id = %s", (ch_id,))[0]
    b2 = db.execute("SELECT power_points FROM users WHERE user_id = %s", (c.from_user.id,))[0]
    
    if b1 < bet or b2 < bet: return await c.answer("❌ Недостаточно мощи!", show_alert=True)
    
    win = random.choice([ch_id, c.from_user.id])
    lose = c.from_user.id if win == ch_id else ch_id
    db.execute("UPDATE users SET power_points = power_points + %s WHERE user_id = %s", (bet, win))
    db.execute("UPDATE users SET power_points = power_points - %s WHERE user_id = %s", (bet, lose))
    
    await c.message.edit_text(f"🏆 В битве победил <b>{c.from_user.first_name if win == c.from_user.id else 'Инициатор'}</b>! (+{bet} 💠)")

@dp.message_handler(content_types=['text'])
async def global_counter(m: types.Message):
    check_user(m.from_user)
    db.execute("UPDATE users SET msg_count = msg_count + 1 WHERE user_id = %s", (m.from_user.id,))

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
            
