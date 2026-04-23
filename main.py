import logging, random, asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.utils import executor
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
import config
from database import db

logging.basicConfig(level=logging.INFO)
bot = Bot(token=config.API_TOKEN, parse_mode="HTML")
dp = Dispatcher(bot)

# --- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ---

def get_mention(uid, name):
    return f'<a href="tg://user?id={uid}">{name}</a>'

def get_evo_status(msgs):
    """Возвращает статус на основе EVO_MAP из config.py"""
    for limit, title in sorted(config.EVO_MAP.items(), reverse=True):
        if msgs >= limit: return title
    return "Вазон 🌱"

async def check_rank(m: types.Message, required_lvl: int):
    """Проверяет, имеет ли юзер нужный ранг"""
    if int(m.from_user.id) == int(config.OWNER_ID): return True
    res = db.execute("SELECT admin_rank FROM users WHERE user_id = %s", (m.from_user.id,))
    current_rank = res[0] if res else 0
    if current_rank >= required_lvl: return True
    await m.reply("❌ Ваша ступень в иерархии слишком низка!")
    return False

# --- 1. КОМАНДА ПОМОЩЬ ---
@dp.message_handler(commands=['help', 'start'])
@dp.message_handler(lambda m: m.text and m.text.lower() == 'помощь')
async def help_cmd(m: types.Message):
    await m.answer(
        "📖 <b>СПРАВОЧНИК ОБИТЕЛИ</b>\n"
        "━━━━━━━━━━━━━━\n"
        "👤 <b>Профиль:</b> <code>Ми</code>, <code>Профиль</code>\n"
        "🎮 <b>Игры:</b> <code>Деп [сумма]</code>, <code>Пвп [сумма]</code>\n"
        "🏛 <b>Кланы:</b> <code>Возглавить пантеон [имя]</code>, <code>Клан</code>\n"
        "🏆 <b>Топы:</b> <code>Сильнейшие</code>, <code>Активчики</code>\n"
        "🛡 <b>Админ:</b> <code>.пд [ранг]</code>, <code>Гив [сумма]</code>, <code>Кара [сумма]</code>\n"
        "━━━━━━━━━━━━━━"
    )

# --- 2. ПРОФИЛЬ И ЭВОЛЮЦИЯ ---
@dp.message_handler(lambda m: m.text and m.text.lower() in ['ми', 'профиль', 'ю*'])
async def profile_cmd(m: types.Message):
    target = m.reply_to_message.from_user if m.reply_to_message else m.from_user
    u = db.execute("SELECT power_points, msg_count, admin_rank, clan_id, clan_role FROM users WHERE user_id = %s", (target.id,))
    
    if not u:
        db.execute("INSERT INTO users (user_id, username, power_points, msg_count, admin_rank) VALUES (%s, %s, 100, 0, 0)", (target.id, target.first_name))
        u = (100, 0, 0, None, None)

    pwr, msgs, adm, c_id, c_role = u
    status = "БОЖЕСТВО 🔱" if int(target.id) == int(config.OWNER_ID) else config.ADM_RANKS.get(adm, "Участник")
    
    clan_line = ""
    if c_id:
        c_name = db.execute("SELECT clan_name FROM clans WHERE clan_id = %s", (c_id,))
        if c_name: clan_line = f"🏛 <b>Пантеон:</b> {c_name[0]} (<i>{c_role}</i>)\n"

    await m.answer(
        f"✨ <b>СВИТОК ОБИТЕЛИ</b>\n━━━━━━━━━━━━━━\n"
        f"👤 <b>Имя:</b> {get_mention(target.id, target.first_name)}\n"
        f"🎖 <b>Статус:</b> <i>{get_evo_status(msgs)}</i>\n"
        f"🔱 <b>Ранг:</b> {status}\n{clan_line}"
        f"⚡️ <b>Мощь:</b> <code>{pwr}</code> 💠\n"
        f"📜 <b>Опыт:</b> <code>{msgs}</code>\n"
        f"━━━━━━━━━━━━━━"
    )

# --- 3. ИГРЫ (ДЕП И ПВП) ---
@dp.message_handler(lambda m: m.text and m.text.lower().startswith(('деп', 'лотерея')))
async def loto_cmd(m: types.Message):
    args = m.text.split()
    bet = int(args[1]) if len(args) > 1 and args[1].isdigit() else 50
    u_data = db.execute("SELECT power_points FROM users WHERE user_id = %s", (m.from_user.id,))
    
    if not u_data or u_data[0] < bet: return await m.reply("❌ Недостаточно мощи!")
    
    mult = random.choices([0, 1, 2, 5, 10], weights=[60, 20, 12, 6, 2])[0]
    win = bet * mult
    db.execute("UPDATE users SET power_points = power_points - %s + %s WHERE user_id = %s", (bet, win, m.from_user.id))
    
    color = "🔴" if mult == 0 else ("🟡" if mult == 1 else "🟢")
    await m.answer(f"{color} <b>ЛОТЕРЕЯ</b>\n━━━━━━━━━━━━━━\n💸 Ставка: {bet}\n💎 Множитель: x{mult}\n💰 Баланс: {u_data[0] - bet + win} 💠\n━━━━━━━━━━━━━━")

@dp.message_handler(lambda m: m.text and m.text.lower().startswith('пвп'))
async def pvp_cmd(m: types.Message):
    if not m.reply_to_message: return await m.reply("Ответь на сообщение цели!")
    bet = int(m.text.split()[1]) if len(m.text.split()) > 1 and m.text.split()[1].isdigit() else 50
    
    kb = InlineKeyboardMarkup().add(InlineKeyboardButton("⚔️ ПРИНЯТЬ", callback_data=f"pvp_{m.from_user.id}_{bet}"))
    await m.answer(f"⚔️ {get_mention(m.from_user.id, m.from_user.first_name)} вызывает на бой {get_mention(m.reply_to_message.from_user.id, m.reply_to_message.from_user.first_name)}!\nСтавка: {bet}", reply_markup=kb)

# --- 4. ТОПЫ ---
@dp.message_handler(lambda m: m.text and m.text.lower() in ['сильнейшие', 'активчики', 'топ пантеонов'])
async def tops_cmd(m: types.Message):
    text = m.text.lower()
    if text == 'сильнейшие':
        rows = db.fetchall("SELECT user_id, username, power_points FROM users ORDER BY power_points DESC LIMIT 10")
        title = "💠 СИЛЬНЕЙШИЕ"
    elif text == 'активчики':
        rows = db.fetchall("SELECT user_id, username, msg_count FROM users ORDER BY msg_count DESC LIMIT 10")
        title = "📈 АКТИВЧИКИ"
    else:
        rows = db.fetchall("SELECT clan_id, clan_name, level FROM clans ORDER BY level DESC LIMIT 10")
        title = "🏆 ПАНТЕОНЫ"

    res = f"<b>{title}</b>\n━━━━━━━━━━━━━━\n"
    for i, r in enumerate(rows, 1):
        name = r[1] if title == "🏆 ПАНТЕОНЫ" else get_mention(r[0], r[1])
        res += f"{i}. {name} — <code>{r[2]}</code>\n"
    await m.answer(res + "━━━━━━━━━━━━━━")

# --- 5. АДМИНКА (.пд, гив, кара, .сбор) ---
@dp.message_handler(lambda m: m.text and m.text.lower().startswith(('.пд', 'гив', 'кара', '.сбор')))
async def admin_cmd(m: types.Message):
    text = m.text.lower()
    args = text.split()

    if text.startswith('.сбор'):
        if not await check_rank(m, 1): return
        users = db.fetchall("SELECT user_id FROM users WHERE msg_count > 0 LIMIT 50")
        mentions = "".join([f'<a href="tg://user?id={u[0]}">\u200b</a>' for u in users])
        return await m.answer(f"🔔 <b>ОБЩИЙ СБОР!</b>\n{mentions}")

    if not m.reply_to_message: return await m.reply("Ответь на сообщение игрока!")
    target = m.reply_to_message.from_user

    if text.startswith('.пд'):
        if int(m.from_user.id) != int(config.OWNER_ID): return
        val = int(args[1]) if len(args) > 1 else 0
        db.execute("UPDATE users SET admin_rank = %s WHERE user_id = %s", (val, target.id))
        await m.answer(f"🔱 <b>СИСТЕМА</b>\n━━━━━━━━━━━━━━\nРанг {get_mention(target.id, target.first_name)} изменен на <code>{val}</code>")

    elif text.startswith('гив'):
        if not await check_rank(m, 3): return
        val = int(args[1]) if len(args) > 1 else 1000
        db.execute("UPDATE users SET power_points = power_points + %s WHERE user_id = %s", (val, target.id))
        await m.answer(f"🎁 <b>ДАР</b>\n━━━━━━━━━━━━━━\n{get_mention(target.id, target.first_name)} получил <code>{val}</code> 💠")

    elif text.startswith('кара'):
        if not await check_rank(m, 2): return
        val = int(args[1]) if len(args) > 1 else 500
        db.execute("UPDATE users SET power_points = GREATEST(0, power_points - %s) WHERE user_id = %s", (val, target.id))
        await m.answer(f"⚡️ <b>КАРА</b>\n━━━━━━━━━━━━━━\nУ {get_mention(target.id, target.first_name)} изъято <code>{val}</code> 💠")

# --- 6. ОБРАБОТЧИК КНОПОК ПВП ---
@dp.callback_query_handler(lambda c: c.data.startswith('pvp_'))
async def pvp_callback(c: types.CallbackQuery):
    _, creator_id, bet = c.data.split('_')
    creator_id, bet = int(creator_id), int(bet)
    if c.from_user.id == creator_id: return await c.answer("Нельзя биться с собой!", show_alert=True)
    
    winner = random.choice([creator_id, c.from_user.id])
    loser = c.from_user.id if winner == creator_id else creator_id
    db.execute("UPDATE users SET power_points = power_points + %s WHERE user_id = %s", (bet, winner))
    db.execute("UPDATE users SET power_points = power_points - %s WHERE user_id = %s", (bet, loser))
    await c.message.edit_text(f"⚔️ <b>ИТОГ БОЯ</b>\n━━━━━━━━━━━━━━\nПобедил: {get_mention(winner, 'Чемпион')}\nЗабрал: <code>{bet}</code> 💠")

# --- 7. ГЛОБАЛЬНЫЙ ОБРАБОТЧИК ОПЫТА (В САМОМ КОНЦЕ) ---
@dp.message_handler(content_types=['text'])
async def xp_handler(m: types.Message):
    db.execute("INSERT INTO users (user_id, username, msg_count, power_points) VALUES (%s, %s, 1, 100) ON CONFLICT (user_id) DO UPDATE SET msg_count = users.msg_count + 1, username = EXCLUDED.username", (m.from_user.id, m.from_user.first_name))
    
