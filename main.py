import logging, random, asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.utils import executor
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
import config
from database import db

# 1. Настройка
logging.basicConfig(level=logging.INFO)
bot = Bot(token=config.API_TOKEN, parse_mode="HTML")
dp = Dispatcher(bot)

# --- ИНСТРУМЕНТАРИЙ ---

def get_mention(uid, name):
    return f'<a href="tg://user?id={uid}">{name}</a>'

def get_evo(msgs):
    """Динамический расчет статуса эволюции"""
    for limit, title in sorted(config.EVO_MAP.items(), reverse=True):
        if msgs >= limit: return title
    return "Вазон 🌱"

async def check_access(m: types.Message, req_lvl: int):
    """Жесткая проверка ранга перед выполнением команды"""
    if int(m.from_user.id) == int(config.OWNER_ID): return True
    res = db.execute("SELECT admin_rank FROM users WHERE user_id = %s", (m.from_user.id,))
    current = res[0] if res else 0
    if current >= req_lvl: return True
    await m.reply("❌ Ваша духовная мощь (ранг) слишком мала!")
    return False

# --- 1. КОМАНДЫ ПОМОЩИ (ОБРАБОТКА ПЕРВОЙ ОЧЕРЕДИ) ---

@dp.message_handler(commands=['help', 'start'])
@dp.message_handler(lambda m: m.text and m.text.lower() == 'помощь')
async def help_logic(m: types.Message):
    help_text = (
        "📖 <b>СПРАВОЧНИК ОБИТЕЛИ</b>\n"
        "━━━━━━━━━━━━━━\n"
        "👤 <b>Профиль:</b> <code>Ми</code>, <code>Профиль</code>, <code>Ю*</code>\n"
        "🎮 <b>Игры:</b> <code>Деп [сумма]</code>, <code>Пвп [сумма]</code>\n"
        "🏛 <b>Кланы:</b> <code>Возглавить пантеон [имя]</code>, <code>Клан</code>\n"
        "🏆 <b>Топы:</b> <code>Сильнейшие</code>, <code>Активчики</code>\n"
        "🛡 <b>Админ:</b> <code>.пд [лвл]</code>, <code>Гив [сумма]</code>, <code>Кара [сумма]</code>\n"
        "━━━━━━━━━━━━━━"
    )
    await m.answer(help_text)

# --- 2. ПРОФИЛЬ ---

@dp.message_handler(lambda m: m.text and m.text.lower() in ['ми', 'профиль', 'ю*'])
async def profile_logic(m: types.Message):
    target = m.reply_to_message.from_user if m.reply_to_message else m.from_user
    u = db.execute("SELECT power_points, msg_count, admin_rank, clan_id, clan_role FROM users WHERE user_id = %s", (target.id,))
    
    if not u:
        db.execute("INSERT INTO users (user_id, username, power_points, msg_count, admin_rank) VALUES (%s, %s, 100, 0, 0)", (target.id, target.first_name))
        u = (100, 0, 0, None, None)

    pwr, msgs, adm, c_id, c_role = u
    status = "БОЖЕСТВО 🔱" if int(target.id) == int(config.OWNER_ID) else config.ADM_RANKS.get(adm, "Участник")
    
    clan_line = ""
    if c_id:
        c_res = db.execute("SELECT clan_name FROM clans WHERE clan_id = %s", (c_id,))
        if c_res: clan_line = f"🏛 <b>Пантеон:</b> {c_res[0]} (<i>{c_role}</i>)\n"

    await m.answer(
        f"✨ <b>СВИТОК ОБИТЕЛИ</b>\n"
        f"━━━━━━━━━━━━━━\n"
        f"👤 <b>Имя:</b> {get_mention(target.id, target.first_name)}\n"
        f"🎖 <b>Статус:</b> <i>{get_evo(msgs)}</i>\n"
        f"🔱 <b>Ранг:</b> {status}\n"
        f"{clan_line}"
        f"⚡️ <b>Мощь:</b> <code>{pwr}</code> 💠\n"
        f"📜 <b>Опыт:</b> <code>{msgs}</code>\n"
        f"━━━━━━━━━━━━━━"
    )

# --- 3. ЛИДЕРБОРДЫ (КЛИКАБЕЛЬНЫЕ НИКИ) ---

@dp.message_handler(lambda m: m.text and m.text.lower() in ['сильнейшие', 'активчики', 'топ пантеонов'])
async def leaderboards_logic(m: types.Message):
    text = m.text.lower()
    if text == 'сильнейшие':
        rows = db.fetchall("SELECT user_id, username, power_points FROM users ORDER BY power_points DESC LIMIT 10")
        title, icon, unit = "СИЛЬНЕЙШИЕ", "💠", "мощи"
    elif text == 'активчики':
        rows = db.fetchall("SELECT user_id, username, msg_count FROM users ORDER BY msg_count DESC LIMIT 10")
        title, icon, unit = "САМЫЕ АКТИВНЫЕ", "📈", "сообщ."
    else:
        rows = db.fetchall("SELECT clan_name, level FROM clans ORDER BY level DESC LIMIT 10")
        title, icon, unit = "ВЕЛИКИЕ ПАНТЕОНЫ", "🏆", "ур."

    res = f"{icon} <b>{title}</b>\n━━━━━━━━━━━━━━\n"
    for i, r in enumerate(rows, 1):
        name = get_mention(r[0], r[1]) if text != 'топ пантеонов' else f"<b>{r[0]}</b>"
        res += f"{i}. {name} — <code>{r[2]}</code> {unit}\n"
    await m.answer(res + "━━━━━━━━━━━━━━")

# --- 4. ИГРЫ (ДЕП И ПВП) ---

@dp.message_handler(lambda m: m.text and m.text.lower().startswith(('деп', 'лотерея')))
async def bet_logic(m: types.Message):
    args = m.text.split()
    bet = int(args[1]) if len(args) > 1 and args[1].isdigit() else 50
    u_pwr = db.execute("SELECT power_points FROM users WHERE user_id = %s", (m.from_user.id,))
    
    if not u_pwr or u_pwr[0] < bet: return await m.reply("❌ Недостаточно мощи!")
    
    mult = random.choices([0, 1, 2, 5, 10], weights=[58, 22, 12, 6, 2])[0]
    win = bet * mult
    db.execute("UPDATE users SET power_points = power_points - %s + %s WHERE user_id = %s", (bet, win, m.from_user.id))
    
    color = "🔴" if mult == 0 else ("🟡" if mult == 1 else "🟢")
    await m.answer(f"{color} <b>ЛОТЕРЕЯ</b>\n━━━━━━━━━━━━━━\n💸 Ставка: {bet}\n💎 Множитель: x{mult}\n💰 Баланс: {u_pwr[0] - bet + win} 💠")

@dp.message_handler(lambda m: m.text and m.text.lower().startswith('пвп'))
async def pvp_init(m: types.Message):
    if not m.reply_to_message: return await m.reply("Ответь на сообщение противника!")
    args = m.text.split()
    bet = int(args[1]) if len(args) > 1 and args[1].isdigit() else 50
    
    p1 = db.execute("SELECT power_points FROM users WHERE user_id = %s", (m.from_user.id,))
    p2 = db.execute("SELECT power_points FROM users WHERE user_id = %s", (m.reply_to_message.from_user.id,))
    
    if not p1 or p1[0] < bet or not p2 or p2[0] < bet: 
        return await m.reply("❌ У одного из вас не хватает мощи!")
    
    kb = InlineKeyboardMarkup().add(InlineKeyboardButton("⚔️ ПРИНЯТЬ БОЙ", callback_data=f"pvp_{m.from_user.id}_{bet}"))
    await m.answer(f"⚔️ {get_mention(m.from_user.id, m.from_user.first_name)} вызывает {get_mention(m.reply_to_message.from_user.id, m.reply_to_message.from_user.first_name)}!\nСтавка: <code>{bet}</code> 💠", reply_markup=kb)

# --- 5. КЛАНЫ (С ИСПРАВЛЕНИЕМ NONETYPE) ---

@dp.message_handler(lambda m: m.text and m.text.lower().startswith(('возглавить', 'клан', 'крах')))
async def clan_system(m: types.Message):
    text = m.text.lower()
    uid = m.from_user.id
    
    if text.startswith('возглавить пантеон'):
        c_name = " ".join(m.text.split()[2:])
        user = db.execute("SELECT power_points, clan_id FROM users WHERE user_id = %s", (uid,))
        if user[1]: return await m.reply("❌ Вы уже в пантеоне!")
        if user[0] < 5000: return await m.reply("❌ Нужно 5000 мощи!")
        
        try:
            # Используем RETURNING для исключения NoneType
            res = db.execute("INSERT INTO clans (clan_name, leader_id) VALUES (%s, %s) RETURNING clan_id", (c_name, uid))
            if res:
                db.execute("UPDATE users SET clan_id = %s, clan_role = 'Глава', power_points = power_points - 5000 WHERE user_id = %s", (res[0], uid))
                await m.answer(f"🏛 Пантеон «{c_name}» основан!")
        except: await m.reply("❌ Клан с таким названием уже существует!")

    elif text == 'клан':
        u = db.execute("SELECT clan_id, clan_role FROM users WHERE user_id = %s", (uid,))
        if not u or not u[0]: return await m.reply("🕵️ Вы пока странник. Используйте <code>возглавить пантеон [имя]</code>")
        c = db.execute("SELECT clan_name, treasury, level FROM clans WHERE clan_id = %s", (u[0],))
        await m.answer(f"🏛 <b>ПАНТЕОН: {c[0]}</b>\n━━━━━━━━━━━━━━\n👤 Роль: {u[1]}\n📈 Уровень: {c[2]}\n💰 Казна: {c[1]} 💠")

# --- 6. АДМИНКА (КАРА, ГИВ, .ПД) ---

@dp.message_handler(lambda m: m.text and m.text.lower().startswith(('.пд', 'гив', 'кара', '.сбор')))
async def admin_panel(m: types.Message):
    text = m.text.lower()
    args = text.split()
    
    if text.startswith('.сбор'):
        if not await check_access(m, 1): return
        users = db.fetchall("SELECT user_id FROM users WHERE msg_count > 0 LIMIT 50")
        mentions = "".join([f'<a href="tg://user?id={u[0]}">\u200b</a>' for u in users])
        return await m.answer(f"🔔 <b>ОБЩИЙ СБОР ОБИТЕЛИ!</b>\n━━━━━━━━━━━━━━\n📢 {m.text[6:] or 'Все в чат!'}\n━━━━━━━━━━━━━━{mentions}")

    if not m.reply_to_message: return await m.reply("Ответь на сообщение цели!")
    target = m.reply_to_message.from_user

    if text.startswith('.пд'):
        if int(m.from_user.id) != int(config.OWNER_ID): return
        val = int(args[1]) if len(args) > 1 else 0
        db.execute("UPDATE users SET admin_rank = %s WHERE user_id = %s", (val, target.id))
        await m.answer(f"⚙️ <b>РАНГ ИЗМЕНЕН</b>\n━━━━━━━━━━━━━━\n👤 {get_mention(target.id, target.first_name)}\n✅ Уровень доступа: <code>{val}</code>")
    
    elif text.startswith('кара'):
        if not await check_access(m, 2): return
        val = int(args[1]) if len(args) > 1 and args[1].isdigit() else 1000
        db.execute("UPDATE users SET power_points = GREATEST(0, power_points - %s) WHERE user_id = %s", (val, target.id))
        await m.answer(f"⚡️ <b>НЕБЕСНАЯ КАРА</b>\n━━━━━━━━━━━━━━\n👤 {get_mention(target.id, target.first_name)}\n📉 Изъято: <code>{val}</code> 💠")

    elif text.startswith('гив'):
        if not await check_access(m, 3): return
        val = int(args[1]) if len(args) > 1 and args[1].isdigit() else 1000
        db.execute("UPDATE users SET power_points = power_points + %s WHERE user_id = %s", (val, target.id))
        await m.answer(f"🔱 <b>ДАР БОГОВ</b>\n━━━━━━━━━━━━━━\n👤 {get_mention(target.id, target.first_name)}\n📈 Выдано: <code>{val}</code> 💠")

# --- 7. CALLBACK ПВП ---
@dp.callback_query_handler(lambda c: c.data.startswith('pvp_'))
async def pvp_callback(c: types.CallbackQuery):
    _, creator_id, bet = c.data.split('_')
    creator_id, bet = int(creator_id), int(bet)
    if c.from_user.id == creator_id: return await c.answer("Нельзя биться с собой!", show_alert=True)
    
    winner = random.choice([creator_id, c.from_user.id])
    loser = c.from_user.id if winner == creator_id else creator_id
    db.execute("UPDATE users SET power_points = power_points + %s WHERE user_id = %s", (bet, winner))
    db.execute("UPDATE users SET power_points = power_points - %s WHERE user_id = %s", (bet, loser))
    await c.message.edit_text(f"⚔️ <b>БОЙ ЗАВЕРШЕН</b>\n━━━━━━━━━━━━━━\n🏆 Победитель: {get_mention(winner, 'Чемпион')}\n💰 Выигрыш: <code>{bet}</code> 💠\n━━━━━━━━━━━━━━")

# --- 8. ГЛОБАЛЬНЫЙ ХЕНДЛЕР ОПЫТА (В САМОМ КОНЦЕ!) ---
@dp.message_handler(content_types=['text'])
async def experience_handler(m: types.Message):
    # Эта функция НЕ должна иметь фильтров, она просто считает сообщения тех, кто не нажал команду
    db.execute("INSERT INTO users (user_id, username, msg_count, power_points) VALUES (%s, %s, 1, 100) ON CONFLICT (user_id) DO UPDATE SET msg_count = users.msg_count + 1, username = EXCLUDED.username", (m.from_user.id, m.from_user.first_name))

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
    
