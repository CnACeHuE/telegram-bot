import logging, random, asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.utils import executor
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
import config
from database import db

logging.basicConfig(level=logging.INFO)
bot = Bot(token=config.API_TOKEN, parse_mode="HTML")
dp = Dispatcher(bot)

# --- УТИЛИТЫ ---
def get_mention(uid, name):
    return f'<a href="tg://user?id={uid}">{name}</a>'

def get_evo(msgs):
    for limit, title in sorted(config.EVO_MAP.items(), reverse=True):
        if msgs >= limit: return title
    return "Вазон 🌱"

# --- ПРОФИЛЬ ---
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

    res = (f"✨ <b>СВИТОК ОБИТЕЛИ</b>\n"
           f"━━━━━━━━━━━━━━\n"
           f"👤 <b>Имя:</b> {get_mention(target.id, target.first_name)}\n"
           f"🎖 <b>Статус:</b> <i>{get_evo(msgs)}</i>\n"
           f"🔱 <b>Ранг:</b> {status}\n"
           f"{clan_line}"
           f"⚡️ <b>Мощь:</b> <code>{pwr}</code> 💠\n"
           f"📜 <b>Опыт:</b> <code>{msgs}</code>\n"
           f"━━━━━━━━━━━━━━")
    await m.answer(res)

# --- ЛИДЕРБОРДЫ (КЛИКАБЕЛЬНЫЕ) ---
@dp.message_handler(lambda m: m.text and m.text.lower() in ['сильнейшие', 'активчики', 'топ пантеонов'])
async def leaderboards(m: types.Message):
    text = m.text.lower()
    res = ""
    
    if text == 'сильнейшие':
        rows = db.fetchall("SELECT user_id, username, power_points FROM users ORDER BY power_points DESC LIMIT 10")
        res = "💠 <b>СИЛЬНЕЙШИЕ В ОБИТЕЛИ</b>\n━━━━━━━━━━━━━━\n"
        for i, r in enumerate(rows, 1):
            res += f"{i}. {get_mention(r[0], r[1])} — <code>{r[2]}</code>\n"
            
    elif text == 'активчики':
        rows = db.fetchall("SELECT user_id, username, msg_count FROM users ORDER BY msg_count DESC LIMIT 10")
        res = "📈 <b>САМЫЕ АКТИВНЫЕ</b>\n━━━━━━━━━━━━━━\n"
        for i, r in enumerate(rows, 1):
            res += f"{i}. {get_mention(r[0], r[1])} — <code>{r[2]}</code>\n"
            
    elif text == 'топ пантеонов':
        rows = db.fetchall("SELECT clan_name, level, treasury FROM clans ORDER BY level DESC LIMIT 10")
        res = "🏆 <b>ВЕЛИКИЕ ПАНТЕОНЫ</b>\n━━━━━━━━━━━━━━\n"
        for i, r in enumerate(rows, 1):
            res += f"{i}. <b>{r[0]}</b> — {r[1]} lvl ({r[2]} 💠)\n"
    
    await m.answer(res + "━━━━━━━━━━━━━━")

# --- ПВП КОМАНДА ---
@dp.message_handler(lambda m: m.text and m.text.lower().startswith('пвп'))
async def pvp_start(m: types.Message):
    if not m.reply_to_message: return await m.reply("Ответь на сообщение противника!")
    
    args = m.text.split()
    bet = int(args[1]) if len(args) > 1 and args[1].isdigit() else 50
    
    p1 = db.execute("SELECT power_points FROM users WHERE user_id = %s", (m.from_user.id,))
    p2 = db.execute("SELECT power_points FROM users WHERE user_id = %s", (m.reply_to_message.from_user.id,))
    
    if not p1 or p1[0] < bet: return await m.reply("❌ У тебя не хватает мощи!")
    if not p2 or p2[0] < bet: return await m.reply("❌ У оппонента не хватает мощи!")
    
    kb = InlineKeyboardMarkup().add(InlineKeyboardButton("⚔️ ПРИНЯТЬ БОЙ", callback_data=f"pvp_{m.from_user.id}_{bet}"))
    await m.answer(f"⚔️ {get_mention(m.from_user.id, m.from_user.first_name)} вызывает на бой "
                   f"{get_mention(m.reply_to_message.from_user.id, m.reply_to_message.from_user.first_name)}!\n"
                   f"💰 Ставка: <code>{bet}</code> 💠", reply_markup=kb)

# --- АДМИН-ИНСТРУМЕНТЫ (ИСПРАВЛЕННАЯ КАРА И ГИВ) ---
@dp.message_handler(lambda m: m.text and m.text.lower().startswith(('.пд', 'гив', 'кара', '.сбор')))
async def admin_panel(m: types.Message):
    if int(m.from_user.id) != int(config.OWNER_ID): return
    
    text = m.text.lower()
    args = text.split()
    
    if text.startswith('.сбор'):
        reason = m.text[6:] or "Всеобщий созыв в Обитель!"
        users = db.fetchall("SELECT user_id FROM users WHERE msg_count > 0 LIMIT 50")
        mentions = "".join([f'<a href="tg://user?id={u[0]}">\u200b</a>' for u in users])
        return await m.answer(f"🔔 <b>ОБЩИЙ СБОР!</b>\n━━━━━━━━━━━━━━\n📢 {reason}\n━━━━━━━━━━━━━━{mentions}")

    if not m.reply_to_message: return await m.reply("Ответь на сообщение цели!")
    target = m.reply_to_message.from_user
    
    if text.startswith('.пд'):
        val = int(args[1]) if len(args) > 1 else 0
        db.execute("UPDATE users SET admin_rank = %s WHERE user_id = %s", (val, target.id))
        await m.answer(f"⚙️ <b>СИСТЕМА</b>\n━━━━━━━━━━━━━━\n👤 {get_mention(target.id, target.first_name)}\n✅ Ранг изменен: <code>{val}</code>")
        
    elif text.startswith('кара'):
        val = int(args[1]) if len(args) > 1 and args[1].isdigit() else 1000
        db.execute("UPDATE users SET power_points = GREATEST(0, power_points - %s) WHERE user_id = %s", (val, target.id))
        await m.answer(f"⚡️ <b>НЕБЕСНАЯ КАРА</b>\n━━━━━━━━━━━━━━\n👤 {get_mention(target.id, target.first_name)}\n📉 Изъято: <code>{val}</code> 💠")
        
    elif text.startswith('гив'):
        val = int(args[1]) if len(args) > 1 and args[1].isdigit() else 1000
        db.execute("UPDATE users SET power_points = power_points + %s WHERE user_id = %s", (val, target.id))
        await m.answer(f"🔱 <b>ДАР БОГОВ</b>\n━━━━━━━━━━━━━━\n👤 {get_mention(target.id, target.first_name)}\n📈 Выдано: <code>{val}</code> 💠")

# --- CALLBACK ОБРАБОТЧИК ---
@dp.callback_query_handler(lambda c: c.data.startswith('pvp_'))
async def pvp_callback(c: types.CallbackQuery):
    _, creator_id, bet = c.data.split('_')
    creator_id, bet = int(creator_id), int(bet)
    
    if c.from_user.id == creator_id:
        return await c.answer("Нельзя сражаться с самим собой!", show_alert=True)
    
    p1 = db.execute("SELECT power_points FROM users WHERE user_id = %s", (creator_id,))[0]
    p2 = db.execute("SELECT power_points FROM users WHERE user_id = %s", (c.from_user.id,))[0]
    
    if p1 < bet or p2 < bet:
        return await c.answer("Недостаточно мощи для начала боя!", show_alert=True)
        
    winner_id = random.choice([creator_id, c.from_user.id])
    loser_id = c.from_user.id if winner_id == creator_id else creator_id
    
    db.execute("UPDATE users SET power_points = power_points + %s WHERE user_id = %s", (bet, winner_id))
    db.execute("UPDATE users SET power_points = power_points - %s WHERE user_id = %s", (bet, loser_id))
    
    await c.message.edit_text(f"⚔️ <b>БОЙ ЗАВЕРШЕН</b>\n━━━━━━━━━━━━━━\n"
                              f"🏆 Победитель: {get_mention(winner_id, 'Чемпион')}\n"
                              f"💀 Проигравший: {get_mention(loser_id, 'Павший')}\n"
                              f"💰 Выигрыш: <code>{bet}</code> 💠\n━━━━━━━━━━━━━━")

# --- ГЛОБАЛЬНЫЙ ОБРАБОТЧИК ОПЫТА ---
@dp.message_handler(content_types=['text'])
async def handler(m: types.Message):
    db.execute("INSERT INTO users (user_id, username, power_points, msg_count) VALUES (%s, %s, 100, 1) "
               "ON CONFLICT (user_id) DO UPDATE SET msg_count = users.msg_count + 1, username = EXCLUDED.username",
               (m.from_user.id, m.from_user.first_name))

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
    
