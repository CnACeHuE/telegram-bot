import logging, random, asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.utils import executor
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
import config
from database import db
from modules.clans import clan_router, dissolve_callback

# Настройка логирования
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

# --- ПРОФИЛЬ (МИ / Ю*) ---
@dp.message_handler(lambda m: m.text and m.text.lower() in ['ми', 'профиль', 'ю*'])
async def profile(m: types.Message):
    target = m.reply_to_message.from_user if m.reply_to_message else m.from_user
    t_id = int(target.id)
    
    u = db.execute("SELECT power_points, msg_count, admin_rank, clan_id, clan_role FROM users WHERE user_id = %s", (t_id,))
    if not u:
        db.execute("INSERT INTO users (user_id, username, power_points, msg_count, admin_rank) VALUES (%s, %s, 100, 0, 0)", (t_id, target.first_name))
        u = (100, 0, 0, None, None)

    pwr, exp, adm_lvl, c_id, c_role = u[0], u[1], u[2], u[3], u[4]
    
    # Ранг из ADM_RANKS
    status = "БОЖЕСТВО 🔱" if t_id == int(config.OWNER_ID) else config.ADM_RANKS.get(adm_lvl, "Участник")
    
    # Информация о клане
    clan_tag = ""
    if c_id:
        c_name = db.execute("SELECT clan_name FROM clans WHERE clan_id = %s", (c_id,))
        clan_tag = f"🏛 <b>Пантеон:</b> {c_name[0]} ({c_role})\n"

    res = (f"✨ <b>СВИТОК ОБИТЕЛИ</b>\n━━━━━━━━━━━━━━\n"
           f"👤 <b>Имя:</b> {get_mention(t_id, target.first_name)}\n"
           f"🎖 <b>Эв. статус:</b> <i>{get_evo_status(exp)}</i>\n"
           f"🔱 <b>Ранг:</b> {status}\n"
           f"{clan_tag}"
           f"⚡️ <b>Мощь:</b> <code>{pwr}</code> 💠\n"
           f"📜 <b>Опыт:</b> <code>{exp}</code>\n━━━━━━━━━━━━━━")
    await m.answer(res)

# --- ЛОТЕРЕЯ (ДЕП) ---
@dp.message_handler(lambda m: m.text and m.text.lower().split()[0] in ['лотерея', 'деп'])
async def loto(m: types.Message):
    args = m.text.split()
    bet = int(args[1]) if len(args) > 1 and args[1].isdigit() else 50
    
    u = db.execute("SELECT power_points FROM users WHERE user_id = %s", (m.from_user.id,))
    if not u or u[0] < bet: return await m.reply("❌ Недостаточно мощи!")
    
    mult = random.choices([0, 1, 2, 5, 10], weights=[55, 25, 12, 6, 2])[0]
    win_sum = bet * mult
    new_bal = u[0] - bet + win_sum
    db.execute("UPDATE users SET power_points = %s WHERE user_id = %s", (new_bal, m.from_user.id))
    
    color = "🔴 ПРОИГРЫШ" if mult == 0 else ("🟡 ПРИ СВОИХ x1" if mult == 1 else f"🟢 ВЫИГРЫШ x{mult}")
    
    res = (f"{color}\n━━━━━━━━━━━━━━\n"
           f"💸 Ставка: {bet}\n"
           f"💎 Получено: {win_sum}\n"
           f"💰 Баланс: {new_bal} 💠")
    await m.answer(res)

# --- ПВП ---
@dp.message_handler(lambda m: m.text and m.text.lower().startswith('пвп'))
async def pvp_cmd(m: types.Message):
    if not m.reply_to_message: return await m.reply("Ответь на сообщение противника!")
    try:
        bet = int(m.text.split()[1]) if len(m.text.split()) > 1 else 50
        p1 = db.execute("SELECT power_points FROM users WHERE user_id = %s", (m.from_user.id,))[0]
        p2 = db.execute("SELECT power_points FROM users WHERE user_id = %s", (m.reply_to_message.from_user.id,))[0]
        
        if p1 < bet or p2 < bet: return await m.reply("Недостаточно мощи для битвы!")
        
        kb = InlineKeyboardMarkup().add(InlineKeyboardButton("⚔️ ПРИНЯТЬ ВЫЗОВ", callback_data=f"pvp_{m.from_user.id}_{bet}"))
        await m.answer(f"⚔️ {get_mention(m.from_user.id, m.from_user.first_name)} вызывает на бой "
                       f"{get_mention(m.reply_to_message.from_user.id, m.reply_to_message.from_user.first_name)}!\nСтавка: {bet} 💠", reply_markup=kb)
    except: pass

@dp.callback_query_handler(lambda c: c.data.startswith('pvp_'))
async def pvp_callback(c: types.CallbackQuery):
    _, creator_id, bet = c.data.split('_')
    creator_id, bet = int(creator_id), int(bet)
    if c.from_user.id == creator_id: return await c.answer("Нельзя биться с собой!", show_alert=True)
    
    winner_id = random.choice([creator_id, c.from_user.id])
    loser_id = c.from_user.id if winner_id == creator_id else creator_id
    
    db.execute("UPDATE users SET power_points = power_points + %s WHERE user_id = %s", (bet, winner_id))
    db.execute("UPDATE users SET power_points = power_points - %s WHERE user_id = %s", (bet, loser_id))
    
    await c.message.edit_text(f"⚔️ <b>БОЙ ОКОНЧЕН!</b>\n━━━━━━━━━━━━━━\nПобедил: {get_mention(winner_id, 'Чемпион')}\nЗабрал <code>{bet}</code> 💠")

# --- ОБРАБОТЧИК РОСПУСКА КЛАНА ---
@dp.callback_query_handler(lambda c: c.data.startswith('dissolve_'))
async def process_dissolve(c: types.CallbackQuery):
    await dissolve_callback(c)

# --- АДМИН-ИНСТРУМЕНТЫ ---
@dp.message_handler(lambda m: m.text and m.text.lower().startswith(('.пд', 'эволюция', 'гив', 'кара')))
async def admin_tools(m: types.Message):
    if int(m.from_user.id) != int(config.OWNER_ID): return
    if not m.reply_to_message: return
    
    args = m.text.split()
    cmd, target = args[0].lower(), m.reply_to_message.from_user
    
    try:
        if cmd in ['.пд', 'эволюция']:
            val = int(args[1])
            db.execute("UPDATE users SET admin_rank = %s WHERE user_id = %s", (val, target.id))
            name = config.ADM_RANKS.get(val, f"Уровень {val}")
            await m.answer(f"🧬 Статус {get_mention(target.id, target.first_name)} изменен на: <b>{name}</b>")
        elif cmd == 'кара':
            db.execute("UPDATE users SET power_points = 0 WHERE user_id = %s", (target.id,))
            await m.answer(f"⚡️ {get_mention(target.id, target.first_name)} поражен карой!")
        elif cmd == 'гив':
            db.execute("UPDATE users SET power_points = power_points + %s WHERE user_id = %s", (int(args[1]), target.id))
            await m.answer(f"🔱 Выдано {args[1]} 💠")
    except: pass

# --- СБОР ---
@dp.message_handler(lambda m: m.text and m.text.lower().startswith('.сбор'))
async def mass_summon(m: types.Message):
    if int(m.from_user.id) != int(config.OWNER_ID): return
    reason = m.text.split(maxsplit=1)[1] if len(m.text.split()) > 1 else "Обитель вызывает всех своих жителей!"
    users = db.fetchall("SELECT user_id FROM users WHERE msg_count > 0 ORDER BY msg_count DESC LIMIT 50")
    mentions = "".join([f'<a href="tg://user?id={u[0]}">\u200b</a>' for u in users])
    await m.answer(f"🔔 <b>ОБЩИЙ СБОР!</b>\n━━━━━━━━━━━━━━\n👤 {get_mention(m.from_user.id, m.from_user.first_name)}\n📢 Объявил: {reason}\n━━━━━━━━━━━━━━{mentions}")

# --- ГЛОБАЛЬНЫЙ ХЕНДЛЕР (ОПЫТ + КЛАНЫ) ---
@dp.message_handler(content_types=['text'])
async def global_handler(m: types.Message):
    # Качаем опыт
    db.execute(
        "INSERT INTO users (user_id, username, power_points, msg_count) VALUES (%s, %s, 100, 1) "
        "ON CONFLICT (user_id) DO UPDATE SET msg_count = users.msg_count + 1, username = EXCLUDED.username",
        (m.from_user.id, m.from_user.first_name)
    )
    
    # Роутер кланов (проверяем ключевые слова)
    first_word = m.text.lower().split()[0] if m.text else ""
    clan_commands = ['возглавить', 'клан', 'депозит', '.принять', 'крах', 'топ']
    if first_word in clan_commands or (len(m.text.split()) > 1 and m.text.lower().startswith('топ кланов')):
        await clan_router(m)

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
                                           
