import logging, random, asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.utils import executor
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
import config
from database import db

# Настройка логирования для отлова ConflictError
logging.basicConfig(level=logging.INFO)
bot = Bot(token=config.API_TOKEN, parse_mode="HTML")
dp = Dispatcher(bot)

# --- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ---
def get_mention(uid, name):
    return f'<a href="tg://user?id={uid}">{name}</a>'

def get_evo_status(msgs):
    """Определяет статус эволюции по EVO_MAP из config.py"""
    for limit, title in sorted(config.EVO_MAP.items(), reverse=True):
        if msgs >= limit:
            return title
    return "Вазон 🌱"

def check_access(user_id, required_rank):
    """Проверка ранга: 999 для OWNER_ID, иначе из БД"""
    if int(user_id) == int(config.OWNER_ID): return True
    res = db.execute("SELECT admin_rank FROM users WHERE user_id = %s", (user_id,))
    current_rank = res[0] if res else 0
    return current_rank >= required_rank

# --- КОМАНДА: ПОМОЩЬ ---
@dp.message_handler(commands=['help', 'start'])
@dp.message_handler(lambda m: m.text and m.text.lower() == 'помощь')
async def help_cmd(m: types.Message):
    help_text = (
        "📖 <b>СПРАВОЧНИК ОБИТЕЛИ</b>\n━━━━━━━━━━━━━━\n"
        "👤 <b>Профиль:</b> <code>Ми</code>, <code>Профиль</code>, <code>Ю*</code>\n"
        "🎮 <b>Игры:</b> <code>Деп [сумма]</code>, <code>Пвп [сумма]</code> (на репли)\n"
        "🏛 <b>Кланы:</b> <code>Возглавить пантеон [имя]</code>, <code>Клан</code>\n"
        "🏆 <b>Топы:</b> <code>Топ пантеонов</code>, <code>Сильнейшие</code>, <code>Активчики</code>\n"
        "🛡 <b>Админ:</b> <code>.пд [ранг]</code>, <code>Гив [сумма]</code>, <code>Кара</code>\n"
        "━━━━━━━━━━━━━━"
    )
    await m.answer(help_text)

# --- ПРОФИЛЬ (Свиток Обители) ---
@dp.message_handler(lambda m: m.text and m.text.lower() in ['ми', 'профиль', 'ю*'])
async def profile(m: types.Message):
    target = m.reply_to_message.from_user if m.reply_to_message else m.from_user
    u = db.execute("SELECT power_points, msg_count, admin_rank, clan_id, clan_role FROM users WHERE user_id = %s", (target.id,))
    
    if not u:
        db.execute("INSERT INTO users (user_id, username, power_points, msg_count, admin_rank) VALUES (%s, %s, 100, 0, 0)", (target.id, target.first_name))
        u = (100, 0, 0, None, None)

    pwr, msgs, adm, c_id, c_role = u[0], u[1], u[2], u[3], u[4]
    status = "БОЖЕСТВО 🔱" if int(target.id) == int(config.OWNER_ID) else config.ADM_RANKS.get(adm, "Участник")
    
    clan_info = ""
    if c_id:
        c_res = db.execute("SELECT clan_name FROM clans WHERE clan_id = %s", (c_id,))
        if c_res:
            clan_info = f"🏛 <b>Пантеон:</b> {c_res[0]} (<i>{c_role}</i>)\n"

    res = (f"✨ <b>СВИТОК ОБИТЕЛИ</b>\n━━━━━━━━━━━━━━\n"
           f"👤 <b>Имя:</b> {get_mention(target.id, target.first_name)}\n"
           f"🎖 <b>Эв. статус:</b> <i>{get_evo_status(msgs)}</i>\n"
           f"🔱 <b>Ранг:</b> {status}\n{clan_info}"
           f"⚡️ <b>Мощь:</b> <code>{pwr}</code> 💠\n"
           f"📜 <b>Опыт:</b> <code>{msgs}</code>\n━━━━━━━━━━━━━━")
    await m.answer(res)

# --- ЛОТЕРЕЯ (Светофор) ---
@dp.message_handler(lambda m: m.text and m.text.lower().split()[0] in ['лотерея', 'деп'])
async def loto(m: types.Message):
    args = m.text.split()
    try:
        bet = int(args[1]) if len(args) > 1 and args[1].isdigit() else 50
        u_data = db.execute("SELECT power_points FROM users WHERE user_id = %s", (m.from_user.id,))
        if not u_data or u_data[0] < bet: return await m.reply("❌ Недостаточно мощи!")
        
        mult = random.choices([0, 1, 2, 5, 10], weights=[55, 25, 12, 6, 2])[0]
        win = bet * mult
        new_bal = u_data[0] - bet + win
        db.execute("UPDATE users SET power_points = %s WHERE user_id = %s", (new_bal, m.from_user.id))
        
        color = "🔴 ПРОИГРЫШ" if mult == 0 else ("🟡 ПРИ СВОИХ" if mult == 1 else f"🟢 ВЫИГРЫШ x{mult}")
        await m.answer(f"{color}\n━━━━━━━━━━━━━━\n💸 Ставка: {bet}\n💎 Получено: {win}\n💰 Баланс: {new_bal} 💠")
    except: pass

# --- ТОПЫ (Сильнейшие, Активчики, Пантеоны) ---
@dp.message_handler(lambda m: m.text and m.text.lower() in ['сильнейшие', 'активчики', 'топ пантеонов', 'топ кланов'])
async def show_tops(m: types.Message):
    text = m.text.lower()
    if text == 'сильнейшие':
        rows = db.fetchall("SELECT username, power_points FROM users ORDER BY power_points DESC LIMIT 10")
        title, icon, unit = "СИЛЬНЕЙШИЕ", "💠", "мощь"
    elif text == 'активчики':
        rows = db.fetchall("SELECT username, msg_count FROM users ORDER BY msg_count DESC LIMIT 10")
        title, icon, unit = "САМЫЕ АКТИВНЫЕ", "📈", "сообщ."
    else:
        rows = db.fetchall("SELECT clan_name, level FROM clans ORDER BY level DESC LIMIT 10")
        title, icon, unit = "ВЕЛИКИЕ ПАНТЕОНЫ", "🏆", "лвл"

    res = f"{icon} <b>{title}:</b>\n\n"
    for i, row in enumerate(rows, 1):
        res += f"{i}. <b>{row[0]}</b> — <code>{row[1]}</code> {unit}\n"
    await m.answer(res)

# --- КЛАНОВАЯ ЛОГИКА (Возглавить, Крах, .принять) ---
@dp.message_handler(lambda m: m.text and m.text.lower().startswith(('возглавить', 'клан', 'крах', '.принять')))
async def clan_logic(m: types.Message):
    text = m.text.lower()
    u_id = m.from_user.id

    if text.startswith('возглавить пантеон'):
        clan_name = " ".join(m.text.split()[2:])
        if not clan_name: return await m.reply("⚠️ Введите название!")
        
        user = db.execute("SELECT power_points, clan_id FROM users WHERE user_id = %s", (u_id,))
        if user and user[1]: return await m.reply("❌ Вы уже в пантеоне!")
        if not user or user[0] < 5000: return await m.reply("❌ Нужно 5000 мощи!")

        try:
            db.execute("INSERT INTO clans (clan_name, leader_id) VALUES (%s, %s)", (clan_name, u_id))
            # Исправляем NoneType
            c_id = db.execute("SELECT clan_id FROM clans WHERE leader_id = %s ORDER BY clan_id DESC", (u_id,))
            if c_id:
                db.execute("UPDATE users SET clan_id = %s, clan_role = 'Глава', power_points = power_points - 5000 WHERE user_id = %s", (c_id[0], u_id))
                await m.answer(f"🏛 Пантеон «{clan_name}» основан!")
        except Exception as e: await m.reply(f"❌ Ошибка: {e}")

    elif text == 'клан':
        u = db.execute("SELECT clan_id, clan_role FROM users WHERE user_id = %s", (u_id,))
        if not u or not u[0]: return await m.reply("🕵️ Вы пока странник.")
        c = db.execute("SELECT clan_name, treasury, level FROM clans WHERE clan_id = %s", (u[0],))
        await m.answer(f"🏛 <b>ПАНТЕОН: {c[0]}</b>\n━━━━━━━━━━━━━━\n👤 Роль: {u[1]}\n📈 Уровень: {c[2]}\n💰 Казна: {c[1]} 💠")

    elif text == '.принять' and m.reply_to_message:
        lead = db.execute("SELECT clan_id, clan_role FROM users WHERE user_id = %s", (u_id,))
        if lead and lead[1] == 'Глава':
            db.execute("UPDATE users SET clan_id = %s, clan_role = 'Участник' WHERE user_id = %s", (lead[0], m.reply_to_message.from_user.id))
            await m.answer("🤝 Принят в Пантеон!")

    elif text == 'крах пантеона':
        u = db.execute("SELECT clan_id, clan_role FROM users WHERE user_id = %s", (u_id,))
        if u and u[1] == 'Глава':
            kb = InlineKeyboardMarkup().add(InlineKeyboardButton("☠️ ПОДТВЕРДИТЬ", callback_data=f"dissolve_{u[0]}"))
            await m.answer("⚠️ Объявить крах пантеона?", reply_markup=kb)

# --- АДМИНКА (.пд, гив, кара, .сбор) ---
@dp.message_handler(lambda m: m.text and m.text.lower().startswith(('.пд', 'гив', 'кара', '.сбор')))
async def admin_tools(m: types.Message):
    if not check_access(m.from_user.id, 1): return # Только для тех, у кого ранг > 0
    
    text = m.text.lower()
    if text.startswith('.сбор'):
        if not check_access(m.from_user.id, 3): return
        users = db.fetchall("SELECT user_id FROM users WHERE msg_count > 0 LIMIT 50")
        mentions = "".join([f'<a href="tg://user?id={u[0]}">\u200b</a>' for u in users])
        return await m.answer(f"🔔 <b>ОБЩИЙ СБОР!</b>\n{mentions}")

    if not m.reply_to_message: return await m.reply("Ответь на сообщение!")
    target = m.reply_to_message.from_user.id
    
    if text.startswith('.пд'):
        if int(m.from_user.id) != int(config.OWNER_ID): return
        val = int(m.text.split()[1]) if len(m.text.split()) > 1 else 0
        db.execute("UPDATE users SET admin_rank = %s WHERE user_id = %s", (val, target))
        await m.answer(f"✅ Ранг изменен на {val}")
    elif 'кара' in text:
        if not check_access(m.from_user.id, 2): return
        db.execute("UPDATE users SET power_points = 0 WHERE user_id = %s", (target,))
        await m.answer("⚡️ Казнен!")
    elif 'гив' in text:
        if not check_access(m.from_user.id, 3): return
        val = int(m.text.split()[-1])
        db.execute("UPDATE users SET power_points = power_points + %s WHERE user_id = %s", (val, target))
        await m.answer(f"💠 Выдано {val}")

# --- CALLBACKS ---
@dp.callback_query_handler(lambda c: c.data.startswith('dissolve_'))
async def dissolve_cb(c: types.CallbackQuery):
    cid = int(c.data.split('_')[1])
    data = db.execute("SELECT leader_id, treasury FROM clans WHERE clan_id = %s", (cid,))
    if data and c.from_user.id == data[0]:
        loot = int(data[1] * 0.65)
        db.execute("UPDATE users SET power_points = power_points + %s, clan_id = NULL, clan_role = NULL WHERE user_id = %s", (loot, c.from_user.id))
        db.execute("UPDATE users SET clan_id = NULL, clan_role = NULL WHERE clan_id = %s", (cid,))
        db.execute("DELETE FROM clans WHERE clan_id = %s", (cid,))
        await c.message.edit_text(f"💥 Пантеон пал! Глава забрал {loot} 💠")

# --- ГЛОБАЛЬНЫЙ ХЕНДЛЕР ---
@dp.message_handler(content_types=['text'])
async def global_handler(m: types.Message):
    db.execute("INSERT INTO users (user_id, username, msg_count) VALUES (%s, %s, 1) ON CONFLICT (user_id) DO UPDATE SET msg_count = users.msg_count + 1", (m.from_user.id, m.from_user.first_name))

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
    
