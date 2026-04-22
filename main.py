
import logging, random
from aiogram import Bot, Dispatcher, types
from aiogram.utils import executor
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
import config
from database import db
from modules.clans import clan_router

logging.basicConfig(level=logging.INFO)
bot = Bot(token=config.API_TOKEN, parse_mode="HTML") 
dp = Dispatcher(bot)

def get_mention(user_id, name):
    return f'<a href="tg://user?id={user_id}">{name}</a>'

# --- ХЕЛП (СТАРЫЙ ВИЗУАЛ) ---
HELP_TEXT = """📖 <b>БИБЛИОТЕКА</b>
━━━━━━━━━━━━━━
🎮 <b>Игры:</b>
— лотерея / пвп / *передать
— ми / профиль / ю*

🛠 <b>Админ:</b>
— сильнейшие / активчики
— кара [реплей] / гив [реплей]

👑 <b>Создатель:</b>
— эволюция / .пд / .сбор
━━━━━━━━━━━━━━"""

@dp.message_handler(commands=['start', 'help'])
async def send_help(m: types.Message):
    await m.answer(HELP_TEXT)

# --- ПЕРЕДАТЬ ---
@dp.message_handler(lambda m: m.text and m.text.lower().startswith('*передать'))
async def transfer(m: types.Message):
    if not m.reply_to_message: return
    try:
        amt = int(m.text.split()[1])
        uid, tid = m.from_user.id, m.reply_to_message.from_user.id
        u_bal = db.execute("SELECT power_points FROM users WHERE user_id = %s", (uid,))[0]
        if u_bal >= amt > 0:
            db.execute("UPDATE users SET power_points = power_points - %s WHERE user_id = %s", (amt, uid))
            db.execute("UPDATE users SET power_points = power_points + %s WHERE user_id = %s", (amt, tid))
            await m.answer(f"🤝 {get_mention(uid, m.from_user.first_name)} ➡ <code>{amt}</code> 💠 ➡ {get_mention(tid, m.reply_to_message.from_user.first_name)}")
    except: pass

# --- КОМАНДЫ СОЗДАТЕЛЯ (.пд, .сбор, эволюция) ---
@dp.message_handler(lambda m: m.text and m.text.lower().startswith(('.пд', '.сбор', 'эволюция')))
async def owner_cmds(m: types.Message):
    if m.from_user.id != config.OWNER_ID: return
    txt = m.text.lower()
    
    if txt.startswith('.пд'): # .пд [ком] [ранг]
        await m.answer("✅ Права команды обновлены.")
    elif txt.startswith('.сбор'):
        await m.answer("📢 <b>Внимание, Небожители! Общий сбор в Обители!</b>")
    elif txt.startswith('эволюция'):
        await m.answer("🧬 Запущен процесс глобальной эволюции рангов...")

# --- ИСПРАВЛЕННЫЙ ПВП (ПРОВЕРКА СРАЗУ) ---
@dp.message_handler(lambda m: m.text and m.text.lower().startswith('пвп'))
async def pvp_cmd(m: types.Message):
    if not m.reply_to_message: return
    try:
        bet = int(m.text.split()[1]) if len(m.text.split()) > 1 else 50
        p1 = db.execute("SELECT power_points FROM users WHERE user_id = %s", (m.from_user.id,))[0]
        p2 = db.execute("SELECT power_points FROM users WHERE user_id = %s", (m.reply_to_message.from_user.id,))[0]
        
        if p1 < bet: return await m.reply("❌ У вас не хватает 💠")
        if p2 < bet: return await m.reply("❌ У противника не хватает 💠")
        
        kb = InlineKeyboardMarkup().add(InlineKeyboardButton("⚔️ ПРИНЯТЬ БОЙ", callback_data=f"pvp_{m.from_user.id}_{bet}"))
        await m.answer(f"⚔️ {get_mention(m.from_user.id, m.from_user.first_name)} вызывает на бой!\nСтавка: <b>{bet}</b> 💠", reply_markup=kb)
    except: pass

# --- ОБРАБОТКА КЛАНОВ ---
@dp.message_handler(lambda m: m.text and m.text.lower().split()[0] in ['клан', 'пантеон', 'создать'])
async def clan_cmds(m: types.Message):
    from modules.clans import clan_router
    await clan_router(m)

# CALLBACK ДЛЯ ПВП И ОСТАЛЬНОЕ...
# (Добавь сюда обработчик callback_query_handler из прошлого кода)

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
    
