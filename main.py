import logging, random, asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.utils import executor
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
import config
from database import db

# 1. Настройка логирования
logging.basicConfig(level=logging.INFO)
bot = Bot(token=config.API_TOKEN, parse_mode="HTML")
dp = Dispatcher(bot)

# --- ВСПОМОГАТЕЛЬНЫЕ ИНСТРУМЕНТЫ ---

def get_mention(uid, name):
    return f'<a href="tg://user?id={uid}">{name}</a>'

def get_evo_status(msgs):
    """Эволюция по EVO_MAP"""
    for limit, title in sorted(config.EVO_MAP.items(), reverse=True):
        if msgs >= limit: return title
    return "Вазон 🌱"

def get_rank_name(lvl):
    """Название ранга из ADM_RANKS"""
    return config.ADM_RANKS.get(lvl, "Участник")

async def check_admin(m: types.Message, req_lvl=1):
    """Проверка прав: Owner всегда 999, остальные по БД"""
    if int(m.from_user.id) == int(config.OWNER_ID): return True
    res = db.execute("SELECT admin_rank FROM users WHERE user_id = %s", (m.from_user.id,))
    if res and res[0] >= req_lvl: return True
    await m.reply("❌ Ваша духовная мощь слишком мала для этой техники!")
    return False

# --- ОБРАБОТЧИКИ КОМАНД ---

# 1. ПОМОЩЬ
@dp.message_handler(commands=['help', 'start'])
@dp.message_handler(lambda m: m.text and m.text.lower() == 'помощь')
async def cmd_help(m: types.Message):
    await m.answer(
        "📖 <b>СПРАВОЧНИК ОБИТЕЛИ</b>\n━━━━━━━━━━━━━━\n"
        "👤 <b>Профиль:</b> <code>Ми</code>, <code>Профиль</code>\n"
        "🎮 <b>Игры:</b> <code>Деп [сумма]</code>, <code>Пвп [сумма]</code>\n"
        "🏛 <b>Кланы:</b> <code>Возглавить пантеон [имя]</code>, <code>Клан</code>\n"
        "🏆 <b>Топы:</b> <code>Сильнейшие</code>, <code>Активчики</code>, <code>Топ пантеонов</code>\n"
        "🛡 <b>Админ:</b> <code>.пд [лвл]</code>, <code>Гив [сумма]</code>, <code>Кара</code>, <code>.сбор</code>\n"
        "━━━━━━━━━━━━━━"
    )

# 2. ПРОФИЛЬ
@dp.message_handler(lambda m: m.text and m.text.lower() in ['ми', 'профиль', 'ю*'])
async def cmd_profile(m: types.Message):
    target = m.reply_to_message.from_user if m.reply_to_message else m.from_user
    u = db.execute("SELECT power_points, msg_count, admin_rank, clan_id, clan_role FROM users WHERE user_id = %s", (target.id,))
    
    if not u:
        db.execute("INSERT INTO users (user_id, username, power_points, msg_count, admin_rank) VALUES (%s, %s, 100, 0, 0)", (target.id, target.first_name))
        u = (100, 0, 0, None, None)

    pwr, msgs, adm, c_id, c_role = u
    status = "БОЖЕСТВО 🔱" if int(target.id) == int(config.OWNER_ID) else get_rank_name(adm)
    
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
        f"📜 <b>Опыт:</b> <code>{msgs}</code>\n━━━━━━━━━━━━━━"
    )

# 3. ТОПЫ (Сильнейшие, Активчики, Пантеоны)
@dp.message_handler(lambda m: m.text and m.text.lower() in ['сильнейшие', 'активчики', 'топ пантеонов', 'топ кланов'])
async def cmd_tops(m: types.Message):
    text = m.text.lower()
    if 'сильнейшие' in text:
        data = db.fetchall("SELECT username, power_points FROM users ORDER BY power_points DESC LIMIT 10")
        title, unit = "СИЛЬНЕЙШИЕ 💠", "мощи"
    elif 'активчики' in text:
        data = db.fetchall("SELECT username, msg_count FROM users ORDER BY msg_count DESC LIMIT 10")
        title, unit = "САМЫЕ АКТИВНЫЕ 📈", "сообщ."
    else:
        data = db.fetchall("SELECT clan_name, level FROM clans ORDER BY level DESC LIMIT 10")
        title, unit = "ВЕЛИКИЕ ПАНТЕОНЫ 🏆", "ур."

    res = f"🏆 <b>{title}</b>\n\n"
    for i, row in enumerate(data, 1):
        res += f"{i}. <b>{row[0]}</b> — {row[1]} {unit}\n"
    await m.answer(res)

# 4. ЛОТЕРЕЯ (Деп)
@dp.message_handler(lambda m: m.text and m.text.lower().startswith(('лотерея', 'деп')))
async def cmd_loto(m: types.Message):
    args = m.text.split()
    bet = int(args[1]) if len(args) > 1 and args[1].isdigit() else 50
    u_pwr = db.execute("SELECT power_points FROM users WHERE user_id = %s", (m.from_user.id,))
    
    if not u_pwr or u_pwr[0] < bet: return await m.reply("❌ Недостаточно мощи!")
    
    mult = random.choices([0, 1, 2, 5, 10], weights=[55, 25, 12, 6, 2])[0]
    win = bet * mult
    db.execute("UPDATE users SET power_points = power_points - %s + %s WHERE user_id = %s", (bet, win, m.from_user.id))
    
    status = "🔴 ПРОИГРЫШ" if mult == 0 else "🟢 ВЫИГРЫШ"
    await m.answer(f"🎰 {status}\n━━━━━━━━━━━━━━\n💸 Ставка: {bet}\n💎 Множитель: x{mult}\n💰 Баланс: {u_pwr[0] - bet + win} 💠")

# 5. КЛАНЫ (Создание, Информация)
@dp.message_handler(lambda m: m.text and m.text.lower().startswith(('возглавить', 'клан', 'крах', '.принять')))
async def cmd_clans(m: types.Message):
    text = m.text.lower()
    uid = m.from_user.id

    if text.startswith('возглавить пантеон'):
        c_name = " ".join(m.text.split()[2:])
        if not c_name: return await m.reply("⚠️ Укажите название!")
        
        user = db.execute("SELECT power_points, clan_id FROM users WHERE user_id = %s", (uid,))
        if user[1]: return await m.reply("❌ Вы уже состоите в Пантеоне!")
        if user[0] < 5000: return await m.reply("❌ Нужно 5000 мощи!")

        db.execute("INSERT INTO clans (clan_name, leader_id) VALUES (%s, %s)", (c_name, uid))
        new_id = db.execute("SELECT clan_id FROM clans WHERE leader_id = %s ORDER BY clan_id DESC", (uid,))
        db.execute("UPDATE users SET clan_id = %s, clan_role = 'Глава', power_points = power_points - 5000 WHERE user_id = %s", (new_id[0], uid))
        await m.answer(f"🏛 Пантеон «{c_name}» успешно основан!")

    elif text == 'клан':
        u = db.execute("SELECT clan_id, clan_role FROM users WHERE user_id = %s", (uid,))
        if not u or not u[0]: return await m.reply("🕵️ Вы пока странник.")
        c = db.execute("SELECT clan_name, treasury, level FROM clans WHERE clan_id = %s", (u[0],))
        await m.answer(f"🏛 <b>ПАНТЕОН: {c[0]}</b>\n━━━━━━━━━━━━━━\n👤 Роль: {u[1]}\n📈 Уровень: {c[2]}\n💰 Казна: {c[1]} 💠")

# 6. АДМИНКА (Кара, Гив, .пд, .сбор)
@dp.message_handler(lambda m: m.text and m.text.lower().startswith(('.пд', 'гив', 'кара', '.сбор')))
async def cmd_admin(m: types.Message):
    text = m.text.lower()
    
    # Команды, требующие OWNER_ID
    if text.startswith('.пд'):
        if int(m.from_user.id) != int(config.OWNER_ID): return
        if not m.reply_to_message: return await m.reply("Ответь на сообщение!")
        lvl = int(text.split()[1]) if len(text.split()) > 1 else 0
        db.execute("UPDATE users SET admin_rank = %s WHERE user_id = %s", (lvl, m.reply_to_message.from_user.id))
        return await m.answer(f"✅ Ранг {get_mention(m.reply_to_message.from_user.id, m.reply_to_message.from_user.first_name)} изменен на {lvl}")

    # Команды для админов (нужна проверка прав)
    if text.startswith('кара'):
        if not await check_admin(m, req_lvl=2): return
        if not m.reply_to_message: return await m.reply("Ответь на сообщение!")
        db.execute("UPDATE users SET power_points = 0 WHERE user_id = %s", (m.reply_to_message.from_user.id,))
        await m.answer("⚡️ Нарушитель поражен карой! Мощь обнулена.")

    elif text.startswith('гив'):
        if not await check_admin(m, req_lvl=3): return
        if not m.reply_to_message: return await m.reply("Ответь на сообщение!")
        val = int(text.split()[-1]) if text.split()[-1].isdigit() else 100
        db.execute("UPDATE users SET power_points = power_points + %s WHERE user_id = %s", (val, m.reply_to_message.from_user.id))
        await m.answer(f"💠 Выдано {val} мощи.")

    elif text.startswith('.сбор'):
        if not await check_admin(m, req_lvl=1): return
        users = db.fetchall("SELECT user_id FROM users WHERE msg_count > 0 LIMIT 50")
        mentions = "".join([f'<a href="tg://user?id={u[0]}">\u200b</a>' for u in users])
        await m.answer(f"🔔 <b>СБОР ОБИТЕЛИ!</b>\nПослание: {m.text[6:] or 'Все сюда!'}{mentions}")

# --- ГЛОБАЛЬНЫЙ ОБРАБОТЧИК (ОПЫТ) ---
@dp.message_handler(content_types=['text'])
async def global_handler(m: types.Message):
    # Эта функция всегда в самом конце, чтобы не мешать командам!
    db.execute("INSERT INTO users (user_id, username, msg_count, power_points) VALUES (%s, %s, 1, 100) "
               "ON CONFLICT (user_id) DO UPDATE SET msg_count = users.msg_count + 1, username = EXCLUDED.username", 
               (m.from_user.id, m.from_user.first_name))

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
    
