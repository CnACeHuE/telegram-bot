import logging, random, asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.utils import executor
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
import config
from database import db
from modules.clans import clan_router

logging.basicConfig(level=logging.INFO)
bot = Bot(token=config.API_TOKEN, parse_mode="HTML")
dp = Dispatcher(bot)

# --- УТИЛИТЫ ---
def get_mention(uid, name):
    return f'<a href="tg://user?id={uid}">{name}</a>'

async def get_user_rank(user_id):
    """Безопасное получение ранга игрока"""
    res = db.execute("SELECT admin_rank FROM users WHERE user_id = %s", (int(user_id),))
    return res[0] if res and res[0] is not None else 0

# --- ХЕЛП (ОФОРМЛЕНИЕ) ---
@dp.message_handler(commands=['help'])
@dp.message_handler(lambda m: m.text and m.text.lower() == 'хелп')
async def help_cmd(m: types.Message):
    text = (
        "✨ <b>БИБЛИОТЕКА ОБИТЕЛИ</b>\n━━━━━━━━━━━━━━\n"
        "🟢 <b>ИГРОВЫЕ:</b>\n"
        "— <code>ми / ю*</code> • Профиль\n"
        "— <code>деп [сумма]</code> • Лотерея\n"
        "— <code>пвп [сумма]</code> • Дуэль (нужен реплай)\n"
        "— <code>сильнейшие</code> • Топ мощи\n\n"
        "🟡 <b>АДМИН:</b>\n"
        "— <code>.сбор [текст]</code> • Общий призыв\n"
        "— <code>.пд [команда] [ранг]</code> • Доступ\n"
        "— <code>эволюция [1-100]</code> • Выдать ранг\n"
        "— <code>гив / кара [сумма]</code> • Баланс\n"
        "━━━━━━━━━━━━━━"
    )
    await m.answer(text)

# --- ПРОФИЛЬ (МИ / Ю*) ---
@dp.message_handler(lambda m: m.text and m.text.lower() in ['ми', 'профиль', 'ю*'])
async def profile(m: types.Message):
    target = m.reply_to_message.from_user if m.reply_to_message else m.from_user
    t_id = int(target.id)
    
    u = db.execute("SELECT power_points, msg_count, admin_rank FROM users WHERE user_id = %s", (t_id,))
    
    if not u:
        db.execute("INSERT INTO users (user_id, username, power_points, msg_count, admin_rank) VALUES (%s, %s, 100, 0, 0) ON CONFLICT DO NOTHING", (t_id, target.first_name))
        u = (100, 0, 0)

    pwr, exp, adm = u[0], u[1], u[2]
    
    # Ранги по сообщениям
    def get_rank_name(msgs):
        if msgs >= 5000: return "Золотая черепаха 🐢"
        if msgs >= 1000: return "Жук 🪲"
        if msgs >= 300: return "Краб 🦀"
        return "Вазон 🌱"

    status = "БОЖЕСТВО 🔱" if t_id == int(config.OWNER_ID) else f"Эволюция: {adm}"
    
    res = (f"✨ <b>СВИТОК ОБИТЕЛИ</b>\n━━━━━━━━━━━━━━\n"
           f"👤 <b>Имя:</b> {get_mention(t_id, target.first_name)}\n"
           f"🎖 <b>Эв. статус:</b> <i>{get_rank_name(exp)}</i>\n"
           f"🔱 <b>Ранг:</b> {status}\n"
           f"⚡️ <b>Мощь:</b> <code>{pwr}</code> 💠\n"
           f"📜 <b>Опыт:</b> <code>{exp}</code>\n━━━━━━━━━━━━━━")
    await m.answer(res)

# --- ТОПЫ ---
@dp.message_handler(lambda m: m.text and m.text.lower() in ['сильнейшие', 'активчики'])
async def tops(m: types.Message):
    is_pwr = "сильнейшие" in m.text.lower()
    col = "power_points" if is_pwr else "msg_count"
    icon = "💠" if is_pwr else "📜"
    
    users = db.fetchall(f"SELECT user_id, username, {col} FROM users ORDER BY {col} DESC LIMIT 10")
    res = f"🏆 <b>{'СИЛЬНЕЙШИЕ' if is_pwr else 'АКТИВЧИКИ'}:</b>\n\n"
    for i, row in enumerate(users, 1):
        res += f"{i}. {get_mention(row[0], row[1])} — <code>{row[2]}</code> {icon}\n"
    await m.answer(res)

# --- КАРА / ГИВ (ТОЛЬКО ДЛЯ OWNER) ---
@dp.message_handler(lambda m: m.text and m.text.lower().startswith(('гив', 'кара')))
async def admin_tools(m: types.Message):
    if int(m.from_user.id) != int(config.OWNER_ID): return
    if not m.reply_to_message: return
    
    args = m.text.split()
    target = m.reply_to_message.from_user
    
    if args[0].lower() == 'кара':
        amt = int(args[1]) if len(args) > 1 and args[1].isdigit() else 999999
        db.execute("UPDATE users SET power_points = GREATEST(0, power_points - %s) WHERE user_id = %s", (amt, target.id))
        await m.answer(f"⚡️ {get_mention(target.id, target.first_name)} поражен карой!")
    elif args[0].lower() == 'гив':
        if len(args) < 2: return
        amt = int(args[1])
        db.execute("UPDATE users SET power_points = power_points + %s WHERE user_id = %s", (amt, target.id))
        await m.answer(f"🔱 {get_mention(target.id, target.first_name)} получил {amt} 💠")

# --- ЛОТЕРЕЯ (ДЕП) ---
@dp.message_handler(lambda m: m.text and m.text.lower().split()[0] in ['лотерея', 'деп'])
async def loto(m: types.Message):
    args = m.text.split()
    bet = int(args[1]) if len(args) > 1 and args[1].isdigit() else 50
    u = db.execute("SELECT power_points FROM users WHERE user_id = %s", (m.from_user.id,))
    if not u or u[0] < bet: return await m.reply("❌ Недостаточно мощи!")
    
    # Светофор: красный (0), желтый (1), зеленый (2, 5, 10)
    mult = random.choices([0, 1, 2, 5, 10], weights=[45, 25, 15, 10, 5])[0]
    new_bal = u[0] - bet + (bet * mult)
    db.execute("UPDATE users SET power_points = %s WHERE user_id = %s", (new_bal, m.from_user.id))
    
    if mult == 0: color, msg = "🔴", "ПРОИГРЫШ"
    elif mult == 1: color, msg = "🟡", "ВОЗВРАТ"
    else: color, msg = "🟢", f"ВЫИГРЫШ x{mult}"
    
    await m.answer(f"{color} <b>{msg}</b>\nБаланс: <code>{new_bal}</code> 💠")

# --- ПВП ---
@dp.message_handler(lambda m: m.text and m.text.lower().startswith('пвп'))
async def pvp_cmd(m: types.Message):
    if not m.reply_to_message: return await m.reply("Ответь на сообщение противника!")
    try:
        bet = int(m.text.split()[1]) if len(m.text.split()) > 1 else 50
        p1 = db.execute("SELECT power_points FROM users WHERE user_id = %s", (m.from_user.id,))[0]
        p2 = db.execute("SELECT power_points FROM users WHERE user_id = %s", (m.reply_to_message.from_user.id,))[0]
        
        if p1 < bet: return await m.reply("❌ У тебя не хватает мощи!")
        if p2 < bet: return await m.reply("❌ У оппонента не хватает мощи!")
        
        kb = InlineKeyboardMarkup().add(InlineKeyboardButton("⚔️ ПРИНЯТЬ ВЫЗОВ", callback_data=f"pvp_{m.from_user.id}_{bet}"))
        await m.answer(f"⚔️ {get_mention(m.from_user.id, m.from_user.first_name)} вызывает на бой "
                       f"{get_mention(m.reply_to_message.from_user.id, m.reply_to_message.from_user.first_name)}!\nСтавка: {bet} 💠", reply_markup=kb)
    except: pass

@dp.callback_query_handler(lambda c: c.data.startswith('pvp_'))
async def pvp_callback(c: types.CallbackQuery):
    _, creator_id, bet = c.data.split('_')
    creator_id, bet = int(creator_id), int(bet)
    if c.from_user.id == creator_id: return await c.answer("Нельзя биться с собой!", show_alert=True)
    
    # Итоговая проверка
    b1 = db.execute("SELECT power_points FROM users WHERE user_id = %s", (creator_id,))[0]
    b2 = db.execute("SELECT power_points FROM users WHERE user_id = %s", (c.from_user.id,))[0]
    if b1 < bet or b2 < bet: return await c.answer("Мощь иссякла!", show_alert=True)
    
    winner_id = random.choice([creator_id, c.from_user.id])
    loser_id = c.from_user.id if winner_id == creator_id else creator_id
    
    db.execute("UPDATE users SET power_points = power_points + %s WHERE user_id = %s", (bet, winner_id))
    db.execute("UPDATE users SET power_points = power_points - %s WHERE user_id = %s", (bet, loser_id))
    
    await c.message.edit_text(f"⚔️ <b>БОЙ ОКОНЧЕН!</b>\nПобедил: {get_mention(winner_id, 'Чемпион')}\nЗабрал {bet} 💠")

# --- .СБОР ---
@dp.message_handler(lambda m: m.text and m.text.lower().startswith('.сбор'))
async def mass_summon(m: types.Message):
    args = m.text.split(maxsplit=1)
    reason = args[1] if len(args) > 1 else "Обитель призывает вас!"
    
    users = db.fetchall("SELECT user_id FROM users WHERE msg_count > 0 ORDER BY msg_count DESC LIMIT 50")
    mentions = "".join([f'<a href="tg://user?id={u[0]}">\u200b</a>' for u in users])
    
    await m.answer(f"🔔 <b>ОБЩИЙ СБОР!</b>\n\nИнициатор: {get_mention(m.from_user.id, m.from_user.first_name)}\nСлова: <i>{reason}</i>{mentions}")

# --- СЧЕТЧИК И КЛАНЫ (В САМОМ НИЗУ!) ---
@dp.message_handler(content_types=['text'])
async def global_counter(m: types.Message):
    # Обновляем опыт
    db.execute(
        "INSERT INTO users (user_id, username, power_points, msg_count) VALUES (%s, %s, 100, 1) "
        "ON CONFLICT (user_id) DO UPDATE SET msg_count = users.msg_count + 1, username = EXCLUDED.username",
        (m.from_user.id, m.from_user.first_name)
    )
    # Если это команда клана — пробрасываем в роутер
    first_word = m.text.lower().split()[0] if m.text else ""
    if first_word in ['клан', 'создать', 'пантеон']:
        await clan_router(m)

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
    
