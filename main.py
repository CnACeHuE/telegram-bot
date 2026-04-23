import logging, random, asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.utils import executor
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
import config
from database import db
# Предполагаем, что логика кланов в отдельном файле, но добавим защиты здесь
from modules.clans import clan_router, dissolve_callback

logging.basicConfig(level=logging.INFO)
bot = Bot(token=config.API_TOKEN, parse_mode="HTML")
dp = Dispatcher(bot)

def get_mention(uid, name):
    return f'<a href="tg://user?id={uid}">{name}</a>'

def get_evo_status(msgs):
    """Статус эволюции по EVO_MAP"""
    for limit, title in sorted(config.EVO_MAP.items(), reverse=True):
        if msgs >= limit: return title
    return "Вазон 🌱"

# --- КОМАНДА ПОМОЩЬ ---
@dp.message_handler(commands=['help', 'start'])
@dp.message_handler(lambda m: m.text and m.text.lower() == 'помощь')
async def help_cmd(m: types.Message):
    help_text = (
        "📖 <b>СПРАВОЧНИК ОБИТЕЛИ</b>\n━━━━━━━━━━━━━━\n"
        "👤 <b>Профиль:</b> <code>Ми</code>, <code>Профиль</code>, <code>Ю*</code>\n"
        "🎮 <b>Игры:</b> <code>Деп [сумма]</code>, <code>Пвп [сумма]</code> (на репли)\n"
        "🏛 <b>Кланы:</b> <code>Возглавить пантеон [имя]</code>, <code>Клан</code>, <code>Топ пантеонов</code>\n"
        "🛡 <b>Админ:</b> <code>.пд [ранг]</code>, <code>Гив [сумма]</code>, <code>Кара</code>\n"
        "━━━━━━━━━━━━━━"
    )
    await m.answer(help_text)

# --- ПРОФИЛЬ ---
@dp.message_handler(lambda m: m.text and m.text.lower() in ['ми', 'профиль', 'ю*'])
async def profile(m: types.Message):
    target = m.reply_to_message.from_user if m.reply_to_message else m.from_user
    u = db.execute("SELECT power_points, msg_count, admin_rank, clan_id, clan_role FROM users WHERE user_id = %s", (target.id,))
    
    if not u:
        db.execute("INSERT INTO users (user_id, username, power_points, msg_count, admin_rank) VALUES (%s, %s, 100, 0, 0)", (target.id, target.first_name))
        u = (100, 0, 0, 0, None, None)

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

# --- ЛОТЕРЕЯ (ДЕП) ---
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
    except Exception as e: logging.error(f"Loto error: {e}")

# --- АДМИНКА (ИСПРАВЛЕНО) ---
@dp.message_handler(lambda m: m.text and m.text.lower().startswith(('.пд', 'эволюция', 'гив', 'кара')))
async def admin_cmds(m: types.Message):
    if int(m.from_user.id) != int(config.OWNER_ID): return
    if not m.reply_to_message: return await m.reply("Ответь на сообщение цели!")
    
    text = m.text.lower()
    args = text.split()
    target_id = m.reply_to_message.from_user.id
    
    try:
        if text.startswith(('.пд', 'эволюция')):
            val = int(args[1]) if len(args) > 1 else 0
            db.execute("UPDATE users SET admin_rank = %s WHERE user_id = %s", (val, target_id))
            await m.answer(f"✅ Статус изменен на: {config.ADM_RANKS.get(val, val)}")
        elif 'кара' in text:
            db.execute("UPDATE users SET power_points = 0 WHERE user_id = %s", (target_id,))
            await m.answer("⚡️ Поражен карой!")
        elif 'гив' in text:
            val = int(args[-1]) if args[-1].isdigit() else 100
            db.execute("UPDATE users SET power_points = power_points + %s WHERE user_id = %s", (val, target_id))
            await m.answer(f"🔱 Выдано {val} 💠")
    except Exception as e: await m.reply(f"⚠️ Ошибка: {e}")

# --- СБОР ---
@dp.message_handler(lambda m: m.text and m.text.lower().startswith('.сбор'))
async def mass_summon(m: types.Message):
    if int(m.from_user.id) != int(config.OWNER_ID): return
    reason = m.text[6:] or "Общий сбор!"
    users = db.fetchall("SELECT user_id FROM users WHERE msg_count > 0 LIMIT 50")
    mentions = "".join([f'<a href="tg://user?id={u[0]}">\u200b</a>' for u in users])
    await m.answer(f"🔔 <b>СБОР:</b> {reason}{mentions}")

# --- КНОПКИ (ПВП И РОСПУСК) ---
@dp.callback_query_handler(lambda c: True)
async def all_callbacks(c: types.CallbackQuery):
    if c.data.startswith('pvp_'):
        _, creator, bet = c.data.split('_'); creator, bet = int(creator), int(bet)
        if c.from_user.id == creator: return await c.answer("Нельзя с собой!", show_alert=True)
        # Логика ПВП...
        winner = random.choice([creator, c.from_user.id])
        db.execute("UPDATE users SET power_points = power_points + %s WHERE user_id = %s", (bet, winner))
        db.execute("UPDATE users SET power_points = power_points - %s WHERE user_id = %s", (bet, creator if winner != creator else c.from_user.id))
        await c.message.edit_text(f"⚔️ Победил {get_mention(winner, 'Герой')}!")
    elif c.data.startswith('dissolve_'):
        await dissolve_callback(c)

# --- ГЛОБАЛЬНЫЙ ОБРАБОТЧИК ---
@dp.message_handler(content_types=['text'])
async def global_handler(m: types.Message):
    # Качаем опыт
    db.execute("INSERT INTO users (user_id, username, msg_count) VALUES (%s, %s, 1) ON CONFLICT (user_id) DO UPDATE SET msg_count = users.msg_count + 1", (m.from_user.id, m.from_user.first_name))
    
    # Роутер кланов (проверка ключевых слов)
    cmd = m.text.lower().split()[0] if m.text else ""
    if cmd in ['возглавить', 'клан', 'депозит', '.принять', 'крах', 'топ', 'активчики', 'сильнейшие']:
        try:
            await clan_router(m)
        except Exception as e:
            logging.error(f"Clan Router Error: {e}")
            await m.reply(f"❌ Ошибка в модуле кланов: {e}")

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
    
