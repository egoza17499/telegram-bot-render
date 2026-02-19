import os
import asyncio
import logging
from datetime import datetime
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from aiohttp import web
from database import (
    init_db, get_user, add_user, update_user, delete_user, get_all_users,
    get_medical, add_medical, check_vlk_status,
    get_checks, add_check, check_exercise_status,
    get_vacation, add_vacation, check_vacation_status
)
from scheduler import run_scheduler

# Настройки
API_TOKEN = os.getenv('BOT_TOKEN')
WEBHOOK_URL = os.getenv('WEBHOOK_URL')
PORT = int(os.getenv('PORT', 8080))

# ID админа (твой Telegram ID)
ADMIN_ID = 393293807 

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)  # ← ЭТО ДОБАВЬ!
bot = Bot(token=API_TOKEN)
dp = Dispatcher()

# Машина состояний
class Form(StatesGroup):
    # Основная анкета
    surname = State()
    name = State()
    patronymic = State()
    rank = State()
    # ВЛК
    vlk_date = State()
    umo_date = State()
    # КБП
    exercise_4_date = State()
    exercise_7_date = State()
    # Отпуск
    vacation_start = State()
    vacation_end = State()
    # Удаление
    confirm_delete = State()
    # Обновление
    update_field = State()
    update_value = State()

# ==================== КОМАНДЫ ====================

@dp.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    init_db()
    user = get_user(message.from_user.id)
    
    if user:
        await message.answer(
            f"👋 Здравствуйте, {user[2]}!\n\n"
            "📋 **Доступные команды:**\n"
            "/profile — Мои данные\n"
            "/update — Редактировать данные\n"
            "/delete — Удалить данные\n"
            "/vlk — ВЛК и УМО\n"
            "/checks — Проверки КБП\n"
            "/vacation — Отпуск\n"
            "/help — Помощь"
        )
    else:
        await message.answer(
            "👋 Привет! Давайте заполним анкету.\n\n"
            "Напишите вашу Фамилию:"
        )
        await state.set_state(Form.surname)

@dp.message(Command("help"))
async def cmd_help(message: types.Message):
    await message.answer(
        "📖 **Справка по командам:**\n\n"
        "📋 **Личные данные:**\n"
        "/profile — Просмотреть мои данные\n"
        "/update — Редактировать данные\n"
        "/delete — Удалить все данные\n\n"
        "🏥 **Медицина:**\n"
        "/vlk — Добавить/изменить ВЛК\n"
        "/umo — Добавить/изменить УМО\n\n"
        "✈️ **Проверки:**\n"
        "/checks — Добавить проверки КБП\n"
        "/ex4 — Упражнение 4 (6 месяцев)\n"
        "/ex7 — Упражнение 7 (12 месяцев)\n\n"
        "🏖️ **Отпуск:**\n"
        "/vacation — Добавить отпуск\n\n"
        "👥 **Админ:**\n"
        "/all — Список всех пользователей"
    )

# ==================== /profile ====================

@dp.message(Command("profile"))
async def cmd_profile(message: types.Message):
    user = get_user(message.from_user.id)
    
    if not user:
        await message.answer("❌ Вы ещё не зарегистрированы. Используйте /start")
        return
    
    medical = get_medical(message.from_user.id)
    checks = get_checks(message.from_user.id)
    vacation = get_vacation(message.from_user.id)
    
    # Статус ВЛК
    vlk_status = ""
    if medical and medical[1]:
        status = check_vlk_status(medical[1])
        if status['vlk_expired']:
            vlk_status = "⛔ **ВЛК:** ИСТЁКЛА! Полёты ЗАПРЕЩЕНЫ!"
        elif status['umo_needed'] and not medical[2]:
            vlk_status = "⚠️ **ВЛК:** Требуется УМО!"
        elif status['remind_30']:
            vlk_status = f"⏰ **ВЛК:** Истекает через {status['days_remaining']} дн."
        else:
            vlk_status = f"✅ **ВЛК:** Действует до {status['days_remaining']} дн."
    
    # Статус КБП
    check_status = ""
    if checks:
        if checks[1]:
            ex4 = check_exercise_status(checks[1], 6)
            if ex4['expired']:
                check_status += "⛔ **Упр.4:** ИСТЕКЛО!\n"
            else:
                check_status += f"✅ **Упр.4:** до {ex4['valid_until']}\n"
        
        if checks[2]:
            ex7 = check_exercise_status(checks[2], 12)
            if ex7['expired']:
                check_status += "⛔ **Упр.7:** ИСТЕКЛО!\n"
            else:
                check_status += f"✅ **Упр.7:** до {ex7['valid_until']}\n"
    
    # Статус отпуска
    vac_status = ""
    if vacation and vacation[2]:
        vac = check_vacation_status(vacation[2])
        if vac['expired']:
            vac_status = "⚠️ **Отпуск:** Прошло больше года!"
        elif vac['remind_30']:
            vac_status = f"⏰ **Отпуск:** Через {vac['days_until_next']} дн. нужен новый"
        else:
            vac_status = f"✅ **Отпуск:** Действует"
    
    await message.answer(
        f"📋 **ВАШИ ДАННЫЕ:**\n\n"
        f"👤 **ФИО:** {user[1]} {user[2]} {user[3] or ''}\n"
        f"🎖️ **Звание:** {user[4] or 'не указано'}\n\n"
        f"{vlk_status}\n"
        f"{check_status}"
        f"{vac_status}\n\n"
        f"📅 **Зарегистрирован:** {user[5]}" if user[5] else ""
    )

# ==================== /delete ====================

@dp.message(Command("delete"))
async def cmd_delete(message: types.Message, state: FSMContext):
    user = get_user(message.from_user.id)
    
    if not user:
        await message.answer("❌ У вас нет данных для удаления.")
        return
    
    await message.answer(
        "⚠️ **ВНИМАНИЕ!**\n\n"
        "Вы действительно хотите удалить ВСЕ свои данные?\n"
        "Это действие НЕЛЬЗЯ отменить!\n\n"
        "Напишите **ДА** для подтверждения или **НЕТ** для отмены:"
    )
    await state.set_state(Form.confirm_delete)

@dp.message(Form.confirm_delete)
async def process_delete_confirm(message: types.Message, state: FSMContext):
    if message.text.upper() == "ДА":
        delete_user(message.from_user.id)
        await message.answer("✅ Ваши данные удалены.")
    else:
        await message.answer("❌ Удаление отменено.")
    
    await state.clear()

# ==================== /update ====================

@dp.message(Command("update"))
async def cmd_update(message: types.Message, state: FSMContext):
    user = get_user(message.from_user.id)
    
    if not user:
        await message.answer("❌ Вы ещё не зарегистрированы.")
        return
    
    await message.answer(
        "✏️ **Редактирование данных**\n\n"
        "Что вы хотите изменить?\n\n"
        "1 — Фамилия\n"
        "2 — Имя\n"
        "3 — Отчество\n"
        "4 — Звание\n"
        "0 — Отмена"
    )
    await state.set_state(Form.update_field)

@dp.message(Form.update_field)
async def process_update_field(message: types.Message, state: FSMContext):
    field = message.text
    
    if field == "0":
        await message.answer("❌ Отменено.")
        await state.clear()
        return
    
    field_map = {"1": "surname", "2": "name", "3": "patronymic", "4": "rank"}
    field_name = {"1": "фамилию", "2": "имя", "3": "отчество", "4": "звание"}
    
    if field not in field_map:
        await message.answer("❌ Неверный выбор. Выберите 0-4:")
        return
    
    await state.update_data(update_field=field_map[field])
    await message.answer(f"Введите новое значение для поля **{field_name[field]}**:")
    await state.set_state(Form.update_value)

@dp.message(Form.update_value)
async def process_update_value(message: types.Message, state: FSMContext):
    data = await state.get_data()
    field = data.get('update_field')
    
    update_user(message.from_user.id, **{field: message.text})
    await message.answer(f"✅ Поле **{field}** обновлено на: {message.text}")
    await state.clear()

# ==================== /all (АДМИН) ====================

@dp.message(Command("all"))
async def cmd_all(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("❌ Доступ только для администратора.")
        return
    
    users = get_all_users()
    
    if not users:
        await message.answer("📭 В базе данных нет пользователей.")
        return
    
    text = "👥 **ВСЕ ПОЛЬЗОВАТЕЛИ:**\n\n"
    for i, user in enumerate(users, 1):
        text += f"{i}. {user[1]} {user[2]} ({user[3]}) — ID: {user[0]}\n"
    
    await message.answer(text)

# ==================== /vlk ====================

@dp.message(Command("vlk"))
async def cmd_vlk(message: types.Message, state: FSMContext):
    await message.answer(
        "🏥 **ВЛК**\n\n"
        "Введите дату прохождения ВЛК в формате **ГГГГ-ММ-ДД**:\n"
        "Пример: 2025-02-19"
    )
    await state.set_state(Form.vlk_date)

@dp.message(Form.vlk_date)
async def process_vlk_date(message: types.Message, state: FSMContext):
    try:
        datetime.strptime(message.text, "%Y-%m-%d")
        add_medical(message.from_user.id, message.text)
        await message.answer(f"✅ ВЛК сохранена: {message.text}")
    except ValueError:
        await message.answer("❌ Неверный формат. Используйте ГГГГ-ММ-ДД:")
        return
    await state.clear()

# ==================== /checks ====================

@dp.message(Command("checks"))
async def cmd_checks(message: types.Message, state: FSMContext):
    await message.answer(
        "✈️ **Проверки КБП**\n\n"
        "Какое упражнение добавить?\n"
        "4 — Упражнение 4 (6 месяцев)\n"
        "7 — Упражнение 7 (12 месяцев)\n"
        "0 — Отмена"
    )
    await state.set_state(Form.exercise_4_date)

@dp.message(Form.exercise_4_date)
async def process_exercise_select(message: types.Message, state: FSMContext):
    if message.text == "0":
        await message.answer("❌ Отменено.")
        await state.clear()
        return
    
    if message.text not in ["4", "7"]:
        await message.answer("❌ Выберите 4, 7 или 0:")
        return
    
    await state.update_data(exercise_num=int(message.text))
    await message.answer("Введите дату проверки в формате **ГГГГ-ММ-ДД**:")
    await state.set_state(Form.exercise_7_date)

@dp.message(Form.exercise_7_date)
async def process_exercise_date(message: types.Message, state: FSMContext):
    try:
        data = await state.get_data()
        exercise = data.get('exercise_num')
        datetime.strptime(message.text, "%Y-%m-%d")
        add_check(message.from_user.id, exercise, message.text)
        await message.answer(f"✅ Упражнение {exercise} сохранено: {message.text}")
    except ValueError:
        await message.answer("❌ Неверный формат. Используйте ГГГГ-ММ-ДД:")
        return
    await state.clear()

# ==================== /vacation ====================

@dp.message(Command("vacation"))
async def cmd_vacation(message: types.Message, state: FSMContext):
    await message.answer(
        "🏖️ **Отпуск**\n\n"
        "Введите дату **начала** отпуска (ГГГГ-ММ-ДД):"
    )
    await state.set_state(Form.vacation_start)

@dp.message(Form.vacation_start)
async def process_vacation_start(message: types.Message, state: FSMContext):
    try:
        datetime.strptime(message.text, "%Y-%m-%d")
        await state.update_data(vac_start=message.text)
        await message.answer("Введите дату **окончания** отпуска (ГГГГ-ММ-ДД):")
        await state.set_state(Form.vacation_end)
    except ValueError:
        await message.answer("❌ Неверный формат. Используйте ГГГГ-ММ-ДД:")
        return

@dp.message(Form.vacation_end)
async def process_vacation_end(message: types.Message, state: FSMContext):
    try:
        data = await state.get_data()
        datetime.strptime(message.text, "%Y-%m-%d")
        add_vacation(message.from_user.id, data['vac_start'], message.text)
        await message.answer(f"✅ Отпуск сохранён: {data['vac_start']} — {message.text}")
    except ValueError:
        await message.answer("❌ Неверный формат. Используйте ГГГГ-ММ-ДД:")
        return
    await state.clear()

# ==================== Веб-сервер ====================

app = web.Application()
SimpleRequestHandler(dispatcher=dp, bot=bot).register(app, path="/webhook")
setup_application(app, dp, bot=bot)

async def on_startup(app: web.Application):
    """Запуск бота: webhook + планировщик"""
    await bot.set_webhook(WEBHOOK_URL)
    # Запуск планировщика напоминаний
    asyncio.create_task(run_scheduler(bot, interval_hours=24))
    logger.info("Планировщик напоминаний запущен!")

async def on_shutdown(app: web.Application):
    """Остановка бота"""
    await bot.delete_webhook()

app.on_startup.append(on_startup)
app.on_shutdown.append(on_shutdown)

if __name__ == "__main__":
    web.run_app(app, host="0.0.0.0", port=PORT)





