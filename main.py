import logging
from aiogram import Bot, Dispatcher, executor, types
import config # Файл config.py в той же папке
from database import db # Файл database.py
from modules.clans import clan_router # Папка modules, файл clans.py

# Включаем логирование, чтобы видеть ошибки в консоли хостинга
logging.basicConfig(level=logging.INFO)
bot = Bot(token=config.API_TOKEN, parse_mode="HTML")
dp = Dispatcher(bot)

# Функция регистрации пользователя
def check_user(u: types.User):
    name = u.first_name.replace("<", "&lt;").replace(">", "&gt;")
    # Исправлено: для PostgreSQL используем %s вместо ?
    db.execute(
        "INSERT INTO users (user_id, username) VALUES (%s, %s) "
        "ON CONFLICT (user_id) DO UPDATE SET username = %s", 
        (u.id, name, name)
    )

# Тестовая команда (проверка связи)
@dp.message_handler(commands=['start', 'test'])
async def test_cmd(m: types.Message):
    check_user(m.from_user) # Теперь регистрация происходит сразу при старте
    await m.answer("✅ <b>Система Обители запущена и видит вас!</b>")

# Обработка кланов
@dp.message_handler(lambda m: m.text and m.text.lower().split()[0] in ['создать', 'пантеон', 'клан', 'призвать', 'внести'])
async def handle_clans(m: types.Message):
    check_user(m.from_user)
    try:
        await clan_router(m)
    except Exception as e:
        logging.error(f"Ошибка в кланах: {e}")
        await m.answer("⚠️ Ошибка в чертогах кланов.")

# Профиль
@dp.message_handler(lambda m: m.text and m.text.lower().split()[0] in ['ми', 'профиль'])
async def profile(m: types.Message):
    check_user(m.from_user)
    # Исправлено: замена ? на %s для совместимости с Railway
    u = db.execute("SELECT power_points, msg_count, clan_role FROM users WHERE user_id = %s", (m.from_user.id,))
    if u:
        await m.answer(
            f"👤 <b>{m.from_user.first_name}</b>\n"
            f"⚡️ Мощь: <code>{u[0]}</code>\n"
            f"📜 Опыт: <code>{u[1]}</code>\n"
            f"🔱 Статус: {u[2]}"
        )
    else:
        await m.answer("Вы еще не записаны в Книгу Судеб.")

# Глобальный сбор опыта
@dp.message_handler(content_types=['text'])
async def gain_exp(m: types.Message):
    # Не обрабатываем команды как обычные сообщения для опыта (по желанию)
    if not m.text.startswith('/'):
        check_user(m.from_user)
        # Исправлено: замена ? на %s
        db.execute("UPDATE users SET msg_count = msg_count + 1 WHERE user_id = %s", (m.from_user.id,))

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
    
