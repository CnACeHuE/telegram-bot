import logging, random, asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.utils import executor
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
import config
from database import db
from modules.clans import clan_router

logging.basicConfig(level=logging.INFO)
bot = Bot(token=config.API_TOKEN, parse_mode="HTML")
dp = Dispatcher(bot)

# --- УТИЛИТЫ ---
async def is_admin(user_id):
    if user_id == config.OWNER_ID: return True
    res = db.execute("SELECT admin_rank FROM users WHERE user_id = %s", (int(user_id),))
    return res and res[0] >= 1 # Даже Junior Admin может делать сбор

def get_mention(uid, name):
    return f'<a href="tg://user?id={uid}">{name}</a>'

async def get_adm_rank_name(lvl):
    ranks = {0: "Житель", 1: "Junior Admin", 2: "Middle Admin", 3: "Senior Admin", 4: "БОЖЕСТВО 🔱"}
    return ranks.get(lvl, "Житель")

# --- 📣 КОМАНДА: .СБОР (ПРИЗЫВ ВСЕХ) ---
@dp.message_handler(lambda m: m.text and m.text.lower() == '.сбор')
async def summon_all(m: types.Message):
    # Проверка на админку, чтобы обычные игроки не спамили
    if not await is_admin(m.from_user.id):
        return await m.reply("❌ <b>Вашего ранга недостаточно для призыва Обители!</b>")

    if m.chat.type == 'private':
        return await m.reply("Призыв работает только в групповых чатах.")

    # Берем последних 50 активных юзеров из базы
    users = db.fetchall("SELECT user_id FROM users WHERE msg_count > 0 ORDER BY msg_count DESC LIMIT 50")
    
    if not users:
        return await m.answer("Свиток призыва пуст. Никто еще не проявил себя.")

    # Формируем сообщение
    mention_list = []
    for user in users:
        # Используем невидимый символ для упоминания, чтобы не загромождать чат текстом
        mention_list.append(f'<a href="tg://user?id={user[0]}">\u200b</a>')

    text = (
        "🔔 <b>ВНИМАНИЕ! ОБЩИЙ СБОР!</b>\n"
        "━━━━━━━━━━━━━━\n"
        f"⚡️ Инициатор: {get_mention(m.from_user.id, m.from_user.first_name)}\n"
        "📜 <i>Все жители призываются в центр Обители для важного дела!</i>\n"
        "━━━━━━━━━━━━━━"
    )
    
    # Склеиваем текст и невидимые теги
    full_message = text + "".join(mention_list)
    await m.answer(full_message)

# --- 👤 ЛИЧНОЕ ДЕЛО (.ПД) ---
@dp.message_handler(lambda m: m.text and m.text.lower() == '.пд')
async def personal_data(m: types.Message):
    target = m.reply_to_message.from_user if m.reply_to_message else m.from_user
    t_id = int(target.id)
    u = db.execute("SELECT power_points, msg_count, admin_rank FROM users WHERE user_id = %s", (t_id,))
    
    if not u: return await m.answer("Данные не найдены.")

    res = (f"📑 <b>ЛИЧНОЕ ДЕЛО:</b> {target.first_name}\n"
           f"━━━━━━━━━━━━━━\n"
           f"🆔 <code>{t_id}</code>\n"
           f"🎭 <b>Статус:</b> {await get_adm_rank_name(u[2])}\n"
           f"💹 <b>Активность:</b> {u[1]} сообщ.\n"
           f"🔋 <b>Запас мощи:</b> {u[0]} 💠\n"
           f"━━━━━━━━━━━━━━")
    await m.answer(res)

# --- 👑 ЭВОЛЮЦИЯ (ВЫДАЧА РАНГОВ) ---
@dp.message_handler(lambda m: m.text and m.text.lower().startswith('эволюция'))
async def set_evolution(m: types.Message):
    if m.from_user.id != config.OWNER_ID: 
        return await m.reply("Только Создатель может управлять эволюцией.")
    
    if not m.reply_to_message:
        return await m.reply("Ответь на сообщение того, чей ранг хочешь изменить.")
    
    try:
        new_lvl = int(m.text.split()[1])
        if not (0 <= new_lvl <= 4): raise ValueError
        
        target = m.reply_to_message.from_user
        db.execute("UPDATE users SET admin_rank = %s WHERE user_id = %s", (new_lvl, target.id))
        rank_name = await get_adm_rank_name(new_lvl)
        await m.answer(f"🧬 <b>ЭВОЛЮЦИЯ!</b>\n{get_mention(target.id, target.first_name)} возвышен до: <b>{rank_name}</b>")
    except:
        await m.reply("Используйте: <code>эволюция [0-4]</code>\n(0-житель, 1-Jun, 2-Mid, 3-Sen, 4-Бог)")

# --- ⚔️ ПВП (БОЙ) ---
@dp.message_handler(lambda m: m.text and m.text.lower().startswith('пвп'))
async def pvp_start(m: types.Message):
    if not m.reply_to_message: return
    try:
        args = m.text.split()
        bet = int(args[1]) if len(args) > 1 and args[1].isdigit() else 50
        
        # Получаем баланс обоих
        p1 = db.execute("SELECT power_points FROM users WHERE user_id = %s", (m.from_user.id,))
        p2 = db.execute("SELECT power_points FROM users WHERE user_id = %s", (m.reply_to_message.from_user.id,))
        
        if not p1 or p1[0] < bet or not p2 or p2[0] < bet:
            return await m.reply("❌ У одного из участников недостаточно мощи!")
        
        kb = InlineKeyboardMarkup().add(InlineKeyboardButton("⚔️ ПРИНЯТЬ ВЫЗОВ", callback_data=f"pvp_{m.from_user.id}_{bet}"))
        await m.answer(f"⚔️ {get_mention(m.from_user.id, m.from_user.first_name)} вызывает на битву "
                       f"{get_mention(m.reply_to_message.from_user.id, m.reply_to_message.from_user.first_name)}!\n"
                       f"💰 Ставка: <b>{bet}</b> 💠", reply_markup=kb)
    except: pass

# --- (ОСТАЛЬНОЙ КОД: МИ, ЛОТЕРЕЯ И GLOBAL_HANDLER ОСТАЮТСЯ ИЗ ПРОШЛОГО ШАГА) ---
