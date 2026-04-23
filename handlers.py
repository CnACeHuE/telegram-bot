import random
from aiogram import types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
import config
from database import db
from utils import get_mention, get_evo, check_access

# --- ИГРЫ ---
async def cmd_dep(m: types.Message):
    args = m.text.split()
    bet = int(args[1]) if len(args) > 1 and args[1].isdigit() else 50
    u_pwr = db.execute("SELECT power_points FROM users WHERE user_id = %s", (m.from_user.id,))
    
    if not u_pwr or u_pwr[0] < bet: return await m.reply("❌ Недостаточно мощи!")
    
    mult = random.choices([0, 1, 2, 5, 10], weights=[58, 22, 12, 6, 2])[0]
    win = bet * mult
    db.execute("UPDATE users SET power_points = power_points - %s + %s WHERE user_id = %s", (bet, win, m.from_user.id))
    
    color = "🔴" if mult == 0 else ("🟡" if mult == 1 else "🟢")
    await m.answer(f"{color} <b>ЛОТЕРЕЯ</b>\n━━━━━━━━━━━━━━\n💸 Ставка: {bet}\n💎 Множитель: x{mult}\n💰 Баланс: {u_pwr[0] - bet + win} 💠")

async def cmd_pvp(m: types.Message):
    if not m.reply_to_message: return await m.reply("Ответь на сообщение противника!")
    args = m.text.split()
    bet = int(args[1]) if len(args) > 1 and args[1].isdigit() else 50
    
    kb = InlineKeyboardMarkup().add(InlineKeyboardButton("⚔️ ПРИНЯТЬ БОЙ", callback_data=f"pvp_{m.from_user.id}_{bet}"))
    await m.answer(f"⚔️ {get_mention(m.from_user.id, m.from_user.first_name)} вызывает на бой!\nСтавка: <code>{bet}</code> 💠", reply_markup=kb)

# --- КЛАНЫ ---
async def cmd_clan(m: types.Message):
    text = m.text.lower()
    uid = m.from_user.id
    
    if text.startswith('возглавить'):
        name = " ".join(m.text.split()[2:])
        if not name: return await m.reply("Введите название!")
        try:
            # RETURNING предотвращает ошибку NoneType
            res = db.execute("INSERT INTO clans (clan_name, leader_id) VALUES (%s, %s) RETURNING clan_id", (name, uid))
            db.execute("UPDATE users SET clan_id = %s, clan_role = 'Глава' WHERE user_id = %s", (res[0], uid))
            await m.answer(f"🏛 Пантеон «{name}» основан!")
        except: await m.reply("❌ Ошибка или название занято.")
    
    elif text == 'клан':
        u = db.execute("SELECT clan_id, clan_role FROM users WHERE user_id = %s", (uid,))
        if not u or not u[0]: return await m.reply("🕵️ Вы странник.")
        c = db.execute("SELECT clan_name, treasury, level FROM clans WHERE clan_id = %s", (u[0],))
        await m.answer(f"🏛 <b>ПАНТЕОН: {c[0]}</b>\n━━━━━━━━━━━━━━\n👤 Роль: {u[1]}\n📈 Ур: {c[2]}\n💰 Казна: {c[1]}")

# --- АДМИНКА (ИСПРАВЛЕННЫЙ ГИВ) ---
async def cmd_admin(m: types.Message):
    text = m.text.lower()
    args = text.split()

    if text.startswith('.сбор'):
        if not await check_access(m, 1): return
        users = db.fetchall("SELECT user_id FROM users WHERE msg_count > 0 LIMIT 50")
        mentions = "".join([f'<a href="tg://user?id={u[0]}">\u200b</a>' for u in users])
        return await m.answer(f"🔔 <b>СБОР ОБИТЕЛИ!</b>\n{mentions}")

    if not m.reply_to_message: return await m.reply("Ответь на сообщение!")
    target = m.reply_to_message.from_user

    if text.startswith('гив'):
        if not await check_access(m, 3): return
        val = int(args[1]) if len(args) > 1 and args[1].isdigit() else 1000
        db.execute("UPDATE users SET power_points = power_points + %s WHERE user_id = %s", (val, target.id))
        await m.answer(f"🔱 <b>ДАР</b>\n👤 {get_mention(target.id, target.first_name)}\n📈 Выдано: <code>{val}</code> 💠")

    elif text.startswith('кара'):
        if not await check_access(m, 2): return
        val = int(args[1]) if len(args) > 1 and args[1].isdigit() else 500
        db.execute("UPDATE users SET power_points = GREATEST(0, power_points - %s) WHERE user_id = %s", (val, target.id))
        await m.answer(f"⚡️ <b>КАРА</b>\n👤 {get_mention(target.id, target.first_name)}\n📉 Изъято: <code>{val}</code> 💠")

    elif text.startswith('.пд'):
        if int(m.from_user.id) != int(config.OWNER_ID): return
        val = int(args[1]) if len(args) > 1 else 0
        db.execute("UPDATE users SET admin_rank = %s WHERE user_id = %s", (val, target.id))
        await m.answer(f"⚙️ Ранг изменен на <code>{val}</code>")
        
