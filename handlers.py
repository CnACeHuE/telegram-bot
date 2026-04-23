import random
from aiogram import types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
import config
from database import db
from utils import get_mention, get_evo, check_access

# --- ПРОФИЛЬ ---
async def cmd_profile(m: types.Message):
    target = m.reply_to_message.from_user if m.reply_to_message else m.from_user
    u = db.execute("SELECT power_points, msg_count, admin_rank, clan_id, clan_role FROM users WHERE user_id = %s", (target.id,))
    
    if not u:
        db.execute("INSERT INTO users (user_id, username, power_points, msg_count, admin_rank) VALUES (%s, %s, 100, 0, 0)", 
                   (target.id, target.first_name))
        u = (100, 0, 0, None, None)

    pwr, msgs, adm, c_id, c_role = u
    status = "БОЖЕСТВО 🔱" if int(target.id) == int(config.OWNER_ID) else config.ADM_RANKS.get(adm, "Участник")
    
    clan_line = ""
    if c_id:
        c_name = db.execute("SELECT clan_name FROM clans WHERE clan_id = %s", (c_id,))
        if c_name: 
            clan_line = f"🏛 <b>Пантеон:</b> {c_name[0]} (<i>{c_role}</i>)\n"

    await m.answer(
        f"✨ <b>СВИТОК ОБИТЕЛИ</b>\n━━━━━━━━━━━━━━\n"
        f"👤 <b>Имя:</b> {get_mention(target.id, target.first_name)}\n"
        f"🎖 <b>Статус:</b> <i>{get_evo(msgs)}</i>\n"
        f"🔱 <b>Ранг:</b> {status}\n{clan_line}"
        f"⚡️ <b>Мощь:</b> <code>{pwr}</code> 💠\n"
        f"📜 <b>Опыт:</b> <code>{msgs}</code>\n━━━━━━━━━━━━━━"
    )

# --- ИГРЫ ---
async def cmd_dep(m: types.Message):
    args = m.text.split()
    bet = int(args[1]) if len(args) > 1 and args[1].isdigit() else 50
    u_pwr = db.execute("SELECT power_points FROM users WHERE user_id = %s", (m.from_user.id,))
    
    if not u_pwr or u_pwr[0] < bet: 
        return await m.reply("❌ Недостаточно мощи!")
    
    mult = random.choices([0, 1, 2, 5, 10], weights=[58, 22, 12, 6, 2])[0]
    win = bet * mult
    db.execute("UPDATE users SET power_points = power_points - %s + %s WHERE user_id = %s", (bet, win, m.from_user.id))
    
    color = "🔴" if mult == 0 else ("🟡" if mult == 1 else "🟢")
    await m.answer(f"{color} <b>ЛОТЕРЕЯ</b>\n━━━━━━━━━━━━━━\n💸 Ставка: {bet}\n💎 Множитель: x{mult}\n💰 Баланс: {u_pwr[0] - bet + win} 💠")

async def cmd_pvp(m: types.Message):
    if not m.reply_to_message: 
        return await m.reply("Ответь на сообщение противника!")
    
    args = m.text.split()
    bet = int(args[1]) if len(args) > 1 and args[1].isdigit() else 50
    
    p1 = db.execute("SELECT power_points FROM users WHERE user_id = %s", (m.from_user.id,))
    p2 = db.execute("SELECT power_points FROM users WHERE user_id = %s", (m.reply_to_message.from_user.id,))
    
    if not p1 or p1[0] < bet:
        return await m.reply(f"❌ {get_mention(m.from_user.id, m.from_user.first_name)}, у тебя маловато мощи!")
    if not p2 or p2[0] < bet:
        return await m.reply(f"❌ У противника недостаточно мощи!")
    
    kb = InlineKeyboardMarkup().add(InlineKeyboardButton("⚔️ ПРИНЯТЬ БОЙ", callback_data=f"pvp_{m.from_user.id}_{bet}"))
    await m.answer(f"⚔️ {get_mention(m.from_user.id, m.from_user.first_name)} вызывает на бой!\nСтавка: <code>{bet}</code> 💠", reply_markup=kb)

# --- ЛИДЕРБОРДЫ ---
async def cmd_tops(m: types.Message):
    text = m.text.lower()
    if 'сильнейшие' in text:
        rows = db.fetchall("SELECT user_id, username, power_points FROM users ORDER BY power_points DESC LIMIT 10")
        title, unit = "СИЛЬНЕЙШИЕ 💠", "мощи"
    else:
        rows = db.fetchall("SELECT user_id, username, msg_count FROM users ORDER BY msg_count DESC LIMIT 10")
        title, unit = "АКТИВЧИКИ 📈", "сообщ."

    res = f"🏆 <b>{title}</b>\n━━━━━━━━━━━━━━\n"
    for i, r in enumerate(rows, 1):
        res += f"{i}. {get_mention(r[0], r[1])} — <code>{r[2]}</code> {unit}\n"
    await m.answer(res + "━━━━━━━━━━━━━━")

# --- КЛАНЫ ---
async def cmd_clan(m: types.Message):
    text = m.text.lower()
    uid = m.from_user.id
    
    if text.startswith('возглавить'):
        parts = m.text.split()
        if len(parts) < 2: return await m.reply("✨ Введите название!")
        
        # Умный захват названия (пропускает слово "пантеон")
        name = " ".join(parts[2:]) if parts[1].lower() == 'пантеон' else " ".join(parts[1:])
            
        try:
            res = db.execute("INSERT INTO clans (clan_name, leader_id) VALUES (%s, %s) RETURNING clan_id", (name, uid))
            db.execute("UPDATE users SET clan_id = %s, clan_role = 'Глава' WHERE user_id = %s", (res[0], uid))
            await m.answer(f"🏛 <b>ВЕЛИКОЕ СОБЫТИЕ</b>\n━━━━━━━━━━━━━━\nПантеон «<b>{name}</b>» официально основан!")
        except Exception: 
            await m.reply("❌ Ошибка: имя занято или вы уже в клане.")
    
    elif text == 'клан':
        u = db.execute("SELECT clan_id, clan_role FROM users WHERE user_id = %s", (uid,))
        if not u or not u[0]: return await m.reply("🕵️ Вы пока вольный странник.")
        c = db.execute("SELECT clan_name, treasury, level FROM clans WHERE clan_id = %s", (u[0],))
        await m.answer(f"🏛 <b>ПАНТЕОН: {c[0]}</b>\n━━━━━━━━━━━━━━\n👤 Роль: {u[1]}\n📈 Ур: {c[2]}\n💰 Казна: {c[1]}")

# --- АДМИНКА ---
async def cmd_admin(m: types.Message):
    text = m.text.lower()
    args = text.split()

    if text.startswith('.сбор'):
        if not await check_access(m, 1): return
        users = db.fetchall("SELECT user_id FROM users WHERE msg_count > 0 LIMIT 50")
        mentions = "".join([f'<a href="tg://user?id={u[0]}">\u200b</a>' for u in users])
        msg = m.text[6:] if len(m.text) > 6 else "Всем явиться в Обитель!"
        return await m.answer(f"🔔 <b>ОБЩИЙ СБОР</b>\n━━━━━━━━━━━━━━\n📢 <b>Призыв:</b> {msg}\n━━━━━━━━━━━━━━\n{mentions}")

    if not m.reply_to_message: return await m.reply("Ответь на сообщение цели!")
    target = m.reply_to_message.from_user

    if text.startswith('гив'):
        if not await check_access(m, 3): return
        val = int(args[1]) if len(args) > 1 and args[1].isdigit() else 1000
        db.execute("UPDATE users SET power_points = power_points + %s WHERE user_id = %s", (val, target.id))
        await m.answer(f"🔱 <b>ДАР</b>\n👤 {get_mention(target.id, target.first_name)} ➜ <code>+{val}</code> 💠")

    elif text.startswith('кара'):
        if not await check_access(m, 2): return
        val = int(args[1]) if len(args) > 1 and args[1].isdigit() else 500
        db.execute("UPDATE users SET power_points = GREATEST(0, power_points - %s) WHERE user_id = %s", (val, target.id))
        await m.answer(f"⚡️ <b>КАРА</b>\n👤 {get_mention(target.id, target.first_name)} ➜ <code>-{val}</code> 💠")

    elif text.startswith('.пд'):
        if int(m.from_user.id) != int(config.OWNER_ID): return
        val = int(args[1]) if len(args) > 1 else 0
        db.execute("UPDATE users SET admin_rank = %s WHERE user_id = %s", (val, target.id))
        await m.answer(f"⚙️ Ранг изменен на <code>{val}</code>")
        
