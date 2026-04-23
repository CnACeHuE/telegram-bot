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

# --- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ---
def get_mention(uid, name):
    return f'<a href="tg://user?id={uid}">{name}</a>'

async def check_perm(m: types.Message, cmd_name: str):
    """Проверка: хватает ли у юзера уровня Эволюции для команды"""
    if m.from_user.id == config.OWNER_ID: return True
    
    # Получаем ранг юзера
    u = db.execute("SELECT admin_rank FROM users WHERE user_id = %s", (m.from_user.id,))
    user_rank = u[0] if u else 0
    
    # Получаем требуемый ранг для команды
    req = db.execute("SELECT min_rank FROM command_rights WHERE cmd_name = %s", (cmd_name,))
    req_rank = req[0] if req else 0
    
    if user_rank >= req_rank:
        return True
    await m.reply(f"⚠️ Ваша эволюция слишком слаба (у вас {user_rank}, нужно {req_rank})")
    return False

# --- КОМАНДА: .ПД (НАСТРОЙКА ПРАВ) ---
@dp.message_handler(lambda m: m.text and m.text.lower().startswith('.пд'))
async def set_cmd_rank(m: types.Message):
    if m.from_user.id != config.OWNER_ID: return
    try:
        args = m.text.split() # .пд лотерея 10
        cmd_name = args[1].lower()
        rank_lvl = int(args[2])
        
        # Создаем таблицу прав, если её нет
        db.execute("CREATE TABLE IF NOT EXISTS command_rights (cmd_name TEXT PRIMARY KEY, min_rank INTEGER)")
        db.execute("INSERT INTO command_rights (cmd_name, min_rank) VALUES (%s, %s) ON CONFLICT (cmd_name) DO UPDATE SET min_rank = EXCLUDED.min_rank", (cmd_name, rank_lvl))
        
        await m.answer(f"✅ Команда <b>{cmd_name}</b> теперь доступна с ранга <b>{rank_lvl}</b>")
    except:
        await m.reply("Используй: <code>.пд [команда] [уровень]</code>")

# --- КОМАНДА: ЭВОЛЮЦИЯ (ВЫДАЧА РАНГА) ---
@dp.message_handler(lambda m: m.text and m.text.lower().startswith('эволюция'))
async def set_evolution(m: types.Message):
    if m.from_user.id != config.OWNER_ID: return
    if not m.reply_to_message: return await m.reply("Ответь на сообщение цели!")
    
    try:
        lvl = int(m.text.split()[1])
        target = m.reply_to_message.from_user
        db.execute("UPDATE users SET admin_rank = %s WHERE user_id = %s", (lvl, target.id))
        await m.answer(f"🧬 {get_mention(target.id, target.first_name)} достиг <b>{lvl} уровня</b> эволюции!")
    except:
        await m.reply("Используй: <code>эволюция [1-100]</code>")

# --- КОМАНДА: ХЕЛП ---
@dp.message_handler(commands=['help'])
@dp.message_handler(lambda m: m.text and m.text.lower() == 'хелп')
async def help_cmd(m: types.Message):
    text = (
        "✨ <b>БИБЛИОТЕКА ОБИТЕЛИ</b>\n━━━━━━━━━━━━━━\n"
        "🎮 <b>РАЗВЛЕЧЕНИЯ:</b>\n"
        "— <code>деп [сумма]</code> • Рискнуть мощью\n"
        "— <code>пвп [сумма]</code> • Вызвать на дуэль\n"
        "— <code>ми / ю*</code> • Ваш профиль\n\n"
        "👑 <b>УПРАВЛЕНИЕ:</b>\n"
        "— <code>.сбор [текст]</code> • Общий призыв\n"
        "— <code>.пд [команда] [уровень]</code> • Права доступа\n"
        "— <code>эволюция [число]</code> • Повысить игрока\n"
        "━━━━━━━━━━━━━━"
    )
    await m.answer(text)

# --- КОМАНДА: .СБОР ---
@dp.message_handler(lambda m: m.text and m.text.lower().startswith('.сбор'))
async def mass_summon(m: types.Message):
    if not await check_perm(m, "сбор"): return
    
    args = m.text.split(maxsplit=1)
    custom_text = args[1] if len(args) > 1 else "Обитель вызывает всех своих жителей!"
    
    users = db.fetchall("SELECT user_id FROM users WHERE msg_count > 0 ORDER BY msg_count DESC LIMIT 50")
    mentions = "".join([f'<a href="tg://user?id={u[0]}">\u200b</a>' for u in users])
    
    ui = (f"🔔 <b>ОБЩИЙ СБОР!</b>\n"
          f"━━━━━━━━━━━━━━\n"
          f"👤 {get_mention(m.from_user.id, m.from_user.first_name)}\n"
          f"📢 <b>Объявил:</b> {custom_text}\n"
          f"━━━━━━━━━━━━━━{mentions}")
    await m.answer(ui)

# --- ЛОТЕРЕЯ (ДЕП) ---
@dp.message_handler(lambda m: m.text and m.text.lower().split()[0] in ['лотерея', 'деп'])
async def loto(m: types.Message):
    if not await check_perm(m, "лотерея"): return
    
    args = m.text.split()
    bet = int(args[1]) if len(args) > 1 and args[1].isdigit() else 50
    u = db.execute("SELECT power_points FROM users WHERE user_id = %s", (m.from_user.id,))
    
    if not u or u[0] < bet: 
        return await m.reply("❌ Ваша мощь слишком мала для такой ставки!")

    mult = random.choices([0, 1, 2, 5, 10], weights=[50, 20, 15, 10, 5])[0]
    new_bal = u[0] - bet + (bet * mult)
    db.execute("UPDATE users SET power_points = %s WHERE user_id = %s", (new_bal, m.from_user.id))

    if mult == 0:
        res, color = "ПРОИГРЫШ", "🔴"
    elif mult == 1:
        res, color = "ВОЗВРАТ", "🟡"
    else:
        res, color = f"ВЫИГРЫШ x{mult}", "🟢"

    ui = (f"{color} <b>{res}</b>\n━━━━━━━━━━━━━━\n"
          f"📉 Ставка: <code>{bet}</code>\n"
          f"💰 Баланс: <code>{new_bal}</code> 💠\n━━━━━━━━━━━━━━")
    await m.answer(ui)

# --- ПВП ---
@dp.message_handler(lambda m: m.text and m.text.lower().startswith('пвп'))
async def pvp_cmd(m: types.Message):
    if not m.reply_to_message: return await m.reply("Ответь на сообщение оппонента!")
    if not await check_perm(m, "пвп"): return

    try:
        args = m.text.split()
        bet = int(args[1]) if len(args) > 1 and args[1].isdigit() else 50
        
        # Проверяем обоих
        p1_val = db.execute("SELECT power_points FROM users WHERE user_id = %s", (m.from_user.id,))[0]
        p2_val = db.execute("SELECT power_points FROM users WHERE user_id = %s", (m.reply_to_message.from_user.id,))[0]

        if p1_val < bet:
            return await m.reply(f"❌ У вас не хватает мощи (нужно {bet})")
        if p2_val < bet:
            return await m.reply(f"❌ У {m.reply_to_message.from_user.first_name} не хватает мощи!")

        kb = InlineKeyboardMarkup().add(InlineKeyboardButton("⚔️ ПРИНЯТЬ ВЫЗОВ", callback_data=f"pvp_ac_{m.from_user.id}_{bet}"))
        await m.answer(f"⚔️ {get_mention(m.from_user.id, m.from_user.first_name)} бросает вызов "
                       f"{get_mention(m.reply_to_message.from_user.id, m.reply_to_message.from_user.first_name)}!\n"
                       f"💰 На кону: <b>{bet}</b> 💠", reply_markup=kb)
    except: pass

@dp.callback_query_handler(lambda c: c.data.startswith('pvp_ac_'))
async def pvp_callback(c: types.CallbackQuery):
    _, _, creator_id, bet = c.data.split('_')
    creator_id, bet = int(creator_id), int(bet)
    
    if c.from_user.id == creator_id:
        return await c.answer("Нельзя воевать с самим собой!", show_alert=True)

    # Итоговая проверка баланса
    b1 = db.execute("SELECT power_points FROM users WHERE user_id = %s", (creator_id,))[0]
    b2 = db.execute("SELECT power_points FROM users WHERE user_id = %s", (c.from_user.id,))[0]
    
    if b1 < bet or b2 < bet:
        return await c.message.edit_text("❌ Битва отменена: у кого-то иссякла мощь!")

    winner_id = random.choice([creator_id, c.from_user.id])
    loser_id = c.from_user.id if winner_id == creator_id else creator_id
    
    db.execute("UPDATE users SET power_points = power_points + %s WHERE user_id = %s", (bet, winner_id))
    db.execute("UPDATE users SET power_points = power_points - %s WHERE user_id = %s", (bet, loser_id))
    
    w_name = (await bot.get_chat(winner_id)).first_name
    await c.message.edit_text(f"⚔️ <b>ИТОГ БИТВЫ</b>\n━━━━━━━━━━━━━━\n🏆 Победитель: {get_mention(winner_id, w_name)}\n"
                              f"💰 Выигрыш: <code>{bet}</code> 💠\n━━━━━━━━━━━━━━")

# --- ГЛОБАЛЬНЫЙ ХЕНДЛЕР ---
@dp.message_handler(content_types=['text'])
async def global_handler(m: types.Message):
    # Обновление статы
    db.execute(
        "INSERT INTO users (user_id, username, power_points, msg_count) VALUES (%s, %s, 100, 1) "
        "ON CONFLICT (user_id) DO UPDATE SET msg_count = users.msg_count + 1, username = EXCLUDED.username",
        (m.from_user.id, m.from_user.first_name)
    )
    if m.text and m.text.lower().split()[0] in ['клан', 'создать', 'пантеон']:
        await clan_router(m)

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
