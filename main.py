import logging
from aiogram import Bot, Dispatcher, executor, types
import config # Файл config.py в той же папке
from database import db # Файл database.py
from modules.clans import clan_router # Папка modules, файл clans.py

# Включаем логирование, чтобы видеть ошибки в консоли хостинга
logging.basicConfig(level=logging.INFO)
bot = Bot(token=config.API_TOKEN, parse_mode="HTML")
dp = Dispatcher(bot)

# Функция регистрации пользователя (без неё команды не сработают)
def check_user(u: types.User):
    name = u.first_name.replace("<", "&lt;").replace(">", "&gt;")
    db.execute("INSERT INTO users (user_id, username) VALUES (?, ?) ON CONFLICT (user_id) DO UPDATE SET username = ?", (u.id, name, name))

# Тестовая команда (проверка связи)
@dp.message_handler(commands=['start', 'test'])
async def test_cmd(m: types.Message):
    await m.answer("✅ Система Обители запущена и видит вас!")

# Обработка кланов
@dp.message_handler(lambda m: m.text and m.text.lower().split()[0] in ['создать', 'пантеон', 'клан', 'призвать', 'внести'])
async def handle_clans(m: types.Message):
    check_user(m.from_user)
    try:
        await clan_router(m)
    except Exception as e:
        logging.error(f"Ошибка в кланах: {e}")
        await m.answer("⚠️ Ошибка в чертогах кланов. Проверьте логи.")

# Профиль
@dp.message_handler(lambda m: m.text and m.text.lower().split()[0] in ['ми', 'профиль'])
async def profile(m: types.Message):
    check_user(m.from_user)
    u = db.execute("SELECT power_points, msg_count, clan_role FROM users WHERE user_id = ?", (m.from_user.id,))
    if u:
        await m.answer(f"👤 <b>{m.from_user.first_name}</b>\n⚡️ Мощь: <code>{u[0]}</code>\n📜 Опыт: <code>{u[1]}</code>\n🔱 Статус: {u[2]}")
    else:
        await m.answer("Вы еще не записаны в Книгу Судеб. Напишите что-нибудь.")

# Глобальный сбор опыта
@dp.message_handler(content_types=['text'])
async def gain_exp(m: types.Message):
    check_user(m.from_user)
    db.execute("UPDATE users SET msg_count = msg_count + 1 WHERE user_id = ?", (m.from_user.id,))

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
    
