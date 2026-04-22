import logging, os, random
from aiogram import Bot, Dispatcher, types
from aiogram.utils import executor
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
import config
from database import db
from modules.clans import clan_router

logging.basicConfig(level=logging.INFO)
bot = Bot(token=config.API_TOKEN, parse_mode="HTML") 
dp = Dispatcher(bot)

# --- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ---
def check_user(u: types.User):
    name = u.first_name.replace("<", "&lt;").replace(">", "&gt;")
    db.execute("INSERT INTO users (user_id, username) VALUES (%s, %s) ON CONFLICT (user_id) DO UPDATE SET username = %s", (u.id, name, name))

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

# --- АДМИН КОМАНДЫ (ГИВ / КАРА) ---
@dp.message_handler(lambda m: m.text and m.text.lower().startswith(('гив', 'божество+', 'божество-', 'кара')))
async def admin_tools(m: types.Message):
    if not await is_admin(m.from_user.id): return
    args = m.text.lower().split()
    cmd = args[0]
    target = m.reply_to_message.from_user if m.reply_to_message else m.from_user
    
    if cmd == 'кара':
        if not m.reply_to_message: return await m.reply("<b>⚠️ Ответь на сообщение грешника!</b>")
        if target.id == config.OWNER_ID: return await m.answer("🛡 Кара бессильна против Создателя.")
        amt = int(args[1]) if len(args) > 1 and args[1].isdigit() else None
        if amt:
            db.execute("UPDATE users SET power_points = GREATEST(0, power_points - %s) WHERE user_id = %s", (amt, target.id))
            await m.answer(f"🔥 {get_mention(target.id, target.first_name)} поражен карой на <code>{amt}</code> 💠")
        else:
            db.execute("UPDATE users SET power_points = 0 WHERE user_id = %s", (target.id,))
            await m.answer(f"⚡️ <b>НЕБЕСНАЯ КАРА!</b> Мощь {get_mention(target.id, target.first_name)} обнулена.")
    
    elif cmd == 'гив':
        if not m.reply_to_message: return await m.reply("<b>⚠️ Ответь на сообщение цели!</b>")
        try:
            amt = int(args[1])
            db.execute("UPDATE users SET power_points = power_points + %s WHERE user_id = %s", (amt, target.id))
            await m.answer(f"🔱 {get_mention(target.id, target.first_name)} получил <code>{amt}</code> 💠 мощи.")
        except: pass

# --- ИГРЫ (ЛОТЕРЕЯ И ПВП) ---
@dp.message_handler(lambda m: m.text and m.text.lower().startswith(('лотерея', 'деп', 'пвп')))
async def games_handler(m: types.Message):
    check_user(m.from_user)
    txt = m.text.lower().split()
    
    if txt[0] in ['лотерея', 'деп']:
        bet = int(txt[1]) if len(txt) > 1 and txt[1].isdigit() else 50
        if bet < 1 or bet > 1000: return await m.reply("<b>⚠️ Ставки от 1 до 1000!</b>")
        
        user = db.execute("SELECT power_points FROM users WHERE user_id = %s", (m.from_user.id,))
        if user[0] < bet: return await m.reply("<b>❌ Недостаточно мощи!</b>")
        
        # Старая система весов и джекпотов
        w = {0: 50, 1: 20, 2: 15, 3: 8, 5: 5, 10: 1.98, 100: 0.02}
        mult = random.choices(list(w.keys()), weights=list(w.values()))[0]
        
        win_amt = bet * mult
        new_bal = user[0] - bet + win_amt
        db.execute("UPDATE users SET power_points = %s WHERE user_id = %s", (new_bal, m.from_user.id))
        
        icon = {100: "💰", 10: "👑", 5: "🟢", 3: "🟢", 2: "🟢", 1: "🟡", 0: "🔴"}.get(mult)
        status = "ДЖЕКПОТ" if mult == 100 else "ВЫИГРЫШ" if mult > 1 else "ПРИ СВОИХ" if mult == 1 else "ПРОИГРЫШ"
        
        res = (f"{icon} <b>{status} x{mult}</b>\n"
               f"━━━━━━━━━━━━━━\n"
               f"💸 Ставка: <code>{bet}</code>\n"
               f"💎 Получено: <code>{win_amt}</code>\n"
               f"💰 Баланс: <code>{new_bal}</code> 💠")
        await m.answer(res)

    elif txt[0] == 'пвп' and m.reply_to_message:
        bet = int(txt[1]) if len(txt) > 1 and txt[1].isdigit() else 50
        u1 = db.execute("SELECT power_points FROM users WHERE user_id = %s", (m.from_user.id,))
        u2 = db.execute("SELECT power_points FROM users WHERE user_id = %s", (m.reply_to_message.from_user.id,))
        
        if u1[0] < bet: return await m.reply(f"❌ У вас не хватает 💠")
        if u2[0] < bet: return await m.reply(f"❌ У противника не хватает 💠")
        
        kb = InlineKeyboardMarkup().add(InlineKeyboardButton("⚔️ ПРИНЯТЬ БОЙ", callback_data=f"pvp_{m.from_user.id}_{bet}"))
        await m.answer(f"⚔️ {get_mention(m.from_user.id, m.from_user.first_name)} вызывает на битву!\nСтавка: <b>{bet}</b> 💠", reply_markup=kb)

# --- СОЦИАЛЬНЫЕ КОМАНДЫ (МИ, ТОПЫ, ПЕРЕДАТЬ) ---
@dp.message_handler(lambda m: m.text and m.text.lower().split()[0] in ['ми', 'профиль', 'ю*', 'сильнейшие', 'активчики', '*передать', '/help', '.пд', '.сбор'])
async def social_handler(m: types.Message):
    check_user(m.from_user)
    cmd = m.text.lower().split()[0]

    if cmd in ['ми', 'профиль', 'ю*']:
        t = m.reply_to_message.from_user if m.reply_to_message else m.from_user
        u = db.execute("SELECT power_points, msg_count, admin_rank, clan_role FROM users WHERE user_id = %s", (t.id,))
        role = "БОЖЕСТВО 🔱" if u[2] >= 3 else get_rank(u[1])
        ui = (f"✨ <b>СВИТОК ОБИТЕЛИ</b>\n━━━━━━━━━━━━━━\n"
              f"👤 <b>Имя:</b> {get_mention(t.id, t.first_name)}\n"
              f"🎖 <b>Ранг:</b> <i>{role}</i>\n"
              f"🔱 <b>Пантеон:</b> {u[3] or 'Нет'}\n"
              f"⚡️ <b>Мощь:</b> <code>{u[0]}</code> 💠\n"
              f"📜 <b>Опыт:</b> <code>{u[1]}</code>\n━━━━━━━━━━━━━━")
        await m.answer(ui)

    elif cmd == 'сильнейшие':
        users = db.fetchall("SELECT user_id, username, power_points FROM users ORDER BY power_points DESC LIMIT 10")
        res = "🏆 <b>СИЛЬНЕЙШИЕ БОГИ:</b>\n\n"
        for i, u in enumerate(users, 1): res += f"{i}. {get_mention(u[0], u[1])} — <code>{u[2]}</code> 💠\n"
        await m.answer(res)

    elif cmd == 'активчики':
        users = db.fetchall("SELECT user_id, username, msg_count FROM users ORDER BY msg_count DESC LIMIT 10")
        res = "🔥 <b>АКТИВЧИКИ ОБИТЕЛИ:</b>\n\n"
        for i, u in enumerate(users, 1): res += f"{i}. {get_mention(u[0], u[1])} — <code>{u[2]}</code> 📜\n"
        await m.answer(res)

    elif cmd == '*передать' and m.reply_to_message:
        try:
            amt = int(m.text.split()[1]); uid, tid = m.from_user.id, m.reply_to_message.from_user.id
            if uid == tid or amt <= 0: return
            bal = db.execute("SELECT power_points FROM users WHERE user_id = %s", (uid,))[0]
            if bal < amt: return await m.reply("❌ Недостаточно мощи!")
            db.execute("UPDATE users SET power_points = power_points - %s WHERE user_id = %s", (amt, uid))
            db.execute("UPDATE users SET power_points = power_points + %s WHERE user_id = %s", (amt, tid))
            await m.answer(f"🤝 {get_mention(uid, m.from_user.first_name)} ➡ <code>{amt}</code> 💠 ➡ {get_mention(tid, m.reply_to_message.from_user.first_name)}")
        except: pass

    elif cmd == '/help':
        await m.answer("📜 <b>СПИСОК КОМАНД:</b>\n• Профиль / Ми\n• Лотерея [сумма]\n• ПВП [сумма] (реплей)\n• Сильнейшие / Активчики\n• *передать [сумма] (реплей)\n• Клан / Пантеон")

# --- ОБРАБОТКА КЛАНОВ ---
@dp.message_handler(lambda m: m.text and m.text.lower().split()[0] in ['создать', 'пантеон', 'клан', 'призвать', 'внести'])
async def clans_handler(m: types.Message):
    await clan_router(m)

# --- CALLBACK ДЛЯ ПВП ---
@dp.callback_query_handler(lambda c: c.data.startswith('pvp_'))
async def pvp_callback(c: types.CallbackQuery):
    _, ch_id, bet = c.data.split('_'); ch_id, bet = int(ch_id), int(bet)
    if c.from_user.id == ch_id: return
    
    b1 = db.execute("SELECT power_points FROM users WHERE user_id = %s", (ch_id,))[0]
    b2 = db.execute("SELECT power_points FROM users WHERE user_id = %s", (c.from_user.id,))[0]
    
    if b1 < bet or b2 < bet: return await c.answer("❌ Недостаточно мощи!", show_alert=True)
    
    win = random.choice([ch_id, c.from_user.id])
    lose = c.from_user.id if win == ch_id else ch_id
    db.execute("UPDATE users SET power_points = power_points + %s WHERE user_id = %s", (bet, win))
    db.execute("UPDATE users SET power_points = power_points - %s WHERE user_id = %s", (bet, lose))
    
    winner_name = (await bot.get_chat_member(c.message.chat.id, win)).user.first_name
    await c.message.edit_text(f"🏆 В битве победил <b>{winner_name}</b>!\n💰 Выигрыш: <code>{bet}</code> 💠")

@dp.message_handler(content_types=['text'])
async def counter(m: types.Message):
    check_user(m.from_user)
    db.execute("UPDATE users SET msg_count = msg_count + 1 WHERE user_id = %s", (m.from_user.id,))

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
    
