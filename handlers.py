import random
from aiogram import types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from database import db
from config import config
import utils

async def cmd_profile(m: types.Message):
    target = m.reply_to_message.from_user if m.reply_to_message else m.from_user
    u = db.register_user(target.id, target.first_name)
    pwr, msgs, adm, c_id, c_role = u
    
    status = "БОЖЕСТВО 🔱" if target.id == config.OWNER_ID else config.ADM_RANKS.get(adm, "Участник")
    clan_line = ""
    if c_id:
        c_res = db.execute("SELECT clan_name FROM clans WHERE clan_id = %s", (c_id,), fetch=True)
        if c_res: clan_line = f"🏛 <b>Пантеон:</b> {c_res[0]} (<i>{c_role}</i>)\n"

    await m.answer(
        f"✨ <b>СВИТОК ОБИТЕЛИ</b>\n━━━━━━━━━━━━━━\n"
        f"👤 <b>Имя:</b> {utils.get_mention(target.id, target.first_name)}\n"
        f"🎖 <b>Статус:</b> <i>{utils.get_evo(msgs)}</i>\n"
        f"🔱 <b>Ранг:</b> {status}\n{clan_line}"
        f"⚡️ <b>Мощь:</b> <code>{pwr}</code> 💠\n"
        f"📜 <b>Опыт:</b> <code>{msgs}</code>\n━━━━━━━━━━━━━━"
    )

async def cmd_dep(m: types.Message):
    args = m.text.split()
    bet = int(args[1]) if len(args) > 1 and args[1].isdigit() else 50
    u_pwr = db.execute("SELECT power_points FROM users WHERE user_id = %s", (m.from_user.id,), fetch=True)
    
    if not u_pwr or u_pwr[0] < bet: return await m.reply("❌ Недостаточно мощи!")
    
    mult = random.choices(config.LOTTERY_MULTIS, weights=config.LOTTERY_WEIGHTS)[0]
    win = bet * mult
    db.execute("UPDATE users SET power_points = power_points - %s + %s WHERE user_id = %s", (bet, win, m.from_user.id))
    
    color = "🔴" if mult == 0 else ("🟡" if mult == 1 else "🟢")
    await m.answer(f"{color} <b>ЛОТЕРЕЯ</b>\n━━━━━━━━━━━━━━\n💸 Ставка: {bet}\n💎 Множитель: x{mult}\n💰 Баланс: {u_pwr[0] - bet + win} 💠")

async def cmd_pvp(m: types.Message):
    if not m.reply_to_message: return await m.reply("Ответь на сообщение противника!")
    args = m.text.split()
    bet = int(args[1]) if len(args) > 1 and args[1].isdigit() else 50
    
    p1 = db.execute("SELECT power_points FROM users WHERE user_id = %s", (m.from_user.id,), fetch=True)
    p2 = db.execute("SELECT power_points FROM users WHERE user_id = %s", (m.reply_to_message.from_user.id,), fetch=True)
    
    if not p1 or p1[0] < bet or not p2 or p2[0] < bet:
        return await m.reply("❌ Недостаточно мощи для битвы!")
    
    kb = InlineKeyboardMarkup().add(InlineKeyboardButton("⚔️ ПРИНЯТЬ БОЙ", callback_data=f"pvp_{m.from_user.id}_{bet}"))
    await m.answer(f"⚔️ {utils.get_mention(m.from_user.id, m.from_user.first_name)} вызывает на бой!\nСтавка: <code>{bet}</code> 💠", reply_markup=kb)

async def cmd_admin(m: types.Message):
    text = m.text.lower()
    if text.startswith('.сбор'):
        if not await utils.check_access(m, 1): return
        users = db.fetchall("SELECT user_id FROM users WHERE msg_count > 0 LIMIT 50")
        mentions = "".join([f'<a href="tg://user?id={u[0]}">\u200b</a>' for u in users])
        await m.answer(f"🔔 <b>ОБЩИЙ СБОР</b>\n━━━━━━━━━━━━━━\n📢 {m.text[6:] if len(m.text) > 6 else 'Явитесь!'}\n━━━━━━━━━━━━━━\n{mentions}")
        
