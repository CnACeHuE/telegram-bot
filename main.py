import logging, random, asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.utils import executor
import config
from database import db
from modules.clans import clan_router, dissolve_callback

logging.basicConfig(level=logging.INFO)
bot = Bot(token=config.API_TOKEN, parse_mode="HTML")
dp = Dispatcher(bot)

# --- ГРЯДКА ПРОВЕРКИ РАНГА ---
def get_user_rank(user_id):
    if int(user_id) == int(config.OWNER_ID): return 999
    res = db.execute("SELECT admin_rank FROM users WHERE user_id = %s", (user_id,))
    return res[0] if res else 0

# --- КОМАНДА .ПД (ВЫДАЧА РАНГА) ---
@dp.message_handler(lambda m: m.text and m.text.lower().startswith('.пд'))
async def set_rank(m: types.Message):
    # Только Создатель может менять ранги
    if int(m.from_user.id) != int(config.OWNER_ID): return
    
    if not m.reply_to_message:
        return await m.reply("⚠️ Чтобы выдать ранг, ответьте на сообщение юзера: <code>.пд [число]</code>")
    
    args = m.text.split()
    rank_val = int(args[1]) if len(args) > 1 and args[1].isdigit() else 0
    target_id = m.reply_to_message.from_user.id
    
    db.execute("UPDATE users SET admin_rank = %s WHERE user_id = %s", (rank_val, target_id))
    status = config.ADM_RANKS.get(rank_val, f"Ранг {rank_val}")
    await m.answer(f"✅ Юзеру {m.reply_to_message.from_user.first_name} присвоен статус: <b>{status}</b>")

# --- КОМАНДА ГИВ (НУЖЕН РАНГ > 2) ---
@dp.message_handler(lambda m: m.text and m.text.lower().startswith('гив'))
async def give_power(m: types.Message):
    my_rank = get_user_rank(m.from_user.id)
    if my_rank < 3: # Допустим, гив доступен от 3 ранга
        return await m.reply("❌ У вас недостаточно полномочий!")
    
    if not m.reply_to_message: return await m.reply("Ответь на сообщение!")
    
    args = m.text.split()
    amount = int(args[1]) if len(args) > 1 and args[1].isdigit() else 100
    db.execute("UPDATE users SET power_points = power_points + %s WHERE user_id = %s", (amount, m.reply_to_message.from_user.id))
    await m.answer(f"💠 Выдано {amount} мощи!")

# --- ПРОФИЛЬ И ОСТАЛЬНОЕ ---
@dp.message_handler(lambda m: m.text and m.text.lower() in ['ми', 'профиль', 'ю*'])
async def profile(m: types.Message):
    target = m.reply_to_message.from_user if m.reply_to_message else m.from_user
    u = db.execute("SELECT power_points, msg_count, admin_rank, clan_id, clan_role FROM users WHERE user_id = %s", (target.id,))
    
    if not u:
        db.execute("INSERT INTO users (user_id, username, power_points, msg_count, admin_rank) VALUES (%s, %s, 100, 0, 0)", (target.id, target.first_name))
        u = (100, 0, 0, None, None)

    pwr, msgs, adm, c_id, c_role = u[0], u[1], u[2], u[3], u[4]
    status = "БОЖЕСТВО 🔱" if int(target.id) == int(config.OWNER_ID) else config.ADM_RANKS.get(adm, "Участник")
    
    clan_line = ""
    if c_id:
        c_res = db.execute("SELECT clan_name FROM clans WHERE clan_id = %s", (c_id,))
        if c_res: clan_line = f"🏛 <b>Пантеон:</b> {c_res[0]} (<i>{c_role}</i>)\n"

    await m.answer(f"✨ <b>СВИТОК ОБИТЕЛИ</b>\n━━━━━━━━━━━━━━\n"
                   f"👤 <b>Имя:</b> {target.first_name}\n"
                   f"🔱 <b>Ранг:</b> {status}\n{clan_line}"
                   f"⚡️ <b>Мощь:</b> <code>{pwr}</code> 💠\n"
                   f"📜 <b>Опыт:</b> <code>{msgs}</code>\n━━━━━━━━━━━━━━")

# --- ОБРАБОТКА CALLBACK ---
@dp.callback_query_handler(lambda c: True)
async def calls(c: types.CallbackQuery):
    if c.data.startswith('dissolve_'): await dissolve_callback(c)

# --- ГЛОБАЛЬНЫЙ ОБРАБОТЧИК ---
@dp.message_handler(content_types=['text'])
async def global_handler(m: types.Message):
    # Сохраняем активность
    db.execute("INSERT INTO users (user_id, username, msg_count) VALUES (%s, %s, 1) ON CONFLICT (user_id) DO UPDATE SET msg_count = users.msg_count + 1, username = EXCLUDED.username", (m.from_user.id, m.from_user.first_name))
    
    # Роутер кланов и топов
    text = m.text.lower()
    cmds = ['сильнейшие', 'активчики', 'топ пантеонов', 'топ кланов', 'возглавить', 'клан', 'крах', '.принять']
    if any(text.startswith(c) for c in cmds):
        await clan_router(m)

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
    
