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
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
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
logger = logging.getLogger(__name__)
bot = Bot(token=API_TOKEN)
dp = Dispatcher()

# Машина состояний
class Form(StatesGroup):
    surname = State()
    name = State()
    patronymic = State()
    rank = State()
    vlk_date = State()
    umo_date = State()
    exercise_4_date = State()
    exercise_7_date = State()
    vacation_start = State()
    vacation_end = State()
    confirm_delete = State()
    update_field = State()
    update_value = State()

# ==================== КНОПКИ БЫСТРЫХ КОМАНД ====================

def get_main_keyboard() -> InlineKeyboardMarkup:
    """Создаёт клавиатуру с основными командами"""
    builder = InlineKeyboardBuilder()
    
    builder.row(
        InlineKeyboardButton(text="📋 Мой профиль", callback_data="profile"),
        InlineKeyboardButton(text="📖 Помощь", callback_data="help")
    )
    
    builder.row(
        InlineKeyboardButton(text="🏥 ВЛК", callback_data="vlk"),
        InlineKeyboardButton(text="✈️ Проверки", callback_data="checks")
    )
    
    builder.row(
        InlineKeyboardButton(text="🏖️ Отпуск", callback_data="vacation"),
        InlineKeyboardButton(text="✏️ Редактировать", callback_data="update")
    )
    
    builder.row(
        InlineKeyboardButton(text="🗑️ Удалить данные", callback_data="delete")
    )
    
    return builder.as_markup()

def get_group_help_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура помощи для группы"""
    builder = InlineKeyboardBuilder()
    
    builder.row(
        InlineKeyboardButton(text="📋 Зарегистрироваться", callback_data="start_reg"),
    )
    
    builder.row(
        InlineKeyboardButton(text="📖 Список команд", callback_data="help"),
        InlineKeyboardButton(text="📊 Мой статус", callback_data="profile")
    )
    
    return builder.as_markup()

# ==================== ФОРМАТИРОВАНИЕ ====================

def format_status_text(text: str, status: str) -> str:
    """Форматирует текст в зависимости от статуса"""
    if status == "critical":  # Красный (истекло)
        return f"<b>{text}</b>"
    elif status == "warning":  # Оранжевый (внимание)
        return f"<b>{text}</b>"
    else:  # Зелёный (норма)
        return f"<b>{text}</b>"

# ==================== КОМАНДЫ ====================

@dp.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    init_db()
    user = get_user(message.from_user.id)
    
    if user:
        full_name = f"{user[1]} {user[2]}"
        if user[3]:
            full_name += f" {user[3]}"
        
        await message.answer(
            f"👋 <b>Здравствуйте, {full_name}!</b>\n\n"
            f"🎖️ {user[4] or 'не указано'}\n\n"
            f"Выберите действие:",
            reply_markup=get_main_keyboard(),
            parse_mode="HTML"
        )
    else:
        await message.answer(
            "👋 <b>Привет! Давайте заполним анкету.</b>\n\n"
            "Напишите вашу <b>фамилию</b>:",
            reply_markup=get_main_keyboard(),
            parse_mode="HTML"
        )
        await state.set_state(Form.surname)

@dp.message(Command("help"))
async def cmd_help(message: types.Message):
    await message.answer(
        "📖 <b>Справка по командам:</b>\n\n"
        "📋 <b>Личные данные:</b>\n"
        "/profile — Просмотреть мои данные\n"
        "/update — Редактировать данные\n"
        "/delete — Удалить все данные\n\n"
        "🏥 <b>Медицина:</b>\n"
        "/vlk — Добавить/изменить ВЛК\n"
        "/umo — Добавить/изменить УМО\n\n"
        "✈️ <b>Проверки:</b>\n"
        "/checks — Добавить проверки КБП\n"
        "/ex4 — Упражнение 4 (6 месяцев)\n"
        "/ex7 — Упражнение 7 (12 месяцев)\n\n"
        "🏖️ <b>Отпуск:</b>\n"
        "/vacation — Добавить отпуск\n\n"
        "👥 <b>Админ:</b>\n"
        "/all — Список всех пользователей (полные данные)\n\n"
        "🔘 <b>Используй кнопки ниже для быстрого доступа!</b>",
        reply_markup=get_main_keyboard(),
        parse_mode="HTML"
    )

@dp.message(Command("menu"))
async def cmd_menu(message: types.Message):
    """Показывает меню кнопок в группе"""
    await message.answer(
        f"👋 {message.from_user.first_name}!\n\n"
        f"📋 <b>Быстрые команды:</b>",
        reply_markup=get_main_keyboard(),
        parse_mode="HTML"
    )

# ==================== ОБРАБОТКА АНКЕТЫ ====================

@dp.message(Form.surname)
async def process_surname(message: types.Message, state: FSMContext):
    if len(message.text) < 2:
        await message.answer("Фамилия слишком короткая. Попробуйте ещё раз:")
        return
    await state.update_data(surname=message.text)
    await message.answer("Теперь введите ваше <b>имя</b>:", parse_mode="HTML")
    await state.set_state(Form.name)

@dp.message(Form.name)
async def process_name(message: types.Message, state: FSMContext):
    if len(message.text) < 2:
        await message.answer("Имя слишком короткое. Попробуйте ещё раз:")
        return
    await state.update_data(name=message.text)
    await message.answer("Введите <b>отчество</b> (или напишите 'нет', если его нет):", parse_mode="HTML")
    await state.set_state(Form.patronymic)

@dp.message(Form.patronymic)
async def process_patronymic(message: types.Message, state: FSMContext):
    patronymic = message.text if message.text.lower() != 'нет' else None
    await state.update_data(patronymic=patronymic)
    await message.answer("Введите ваше <b>звание</b> (или напишите 'нет'):", parse_mode="HTML")
    await state.set_state(Form.rank)

@dp.message(Form.rank)
async def process_rank(message: types.Message, state: FSMContext):
    rank = message.text if message.text.lower() != 'нет' else None
    
    data = await state.get_data()
    success = add_user(
        telegram_id=message.from_user.id,
        surname=data['surname'],
        name=data['name'],
        patronymic=data.get('patronymic'),
        rank=rank
    )
    
    if success:
        full_name = f"{data['surname']} {data['name']}"
        if data.get('patronymic'):
            full_name += f" {data['patronymic']}"
        
        await message.answer(
            f"✅ <b>Данные сохранены!</b>\n\n"
            f"👤 {full_name}\n"
            f"🎖️ {rank or 'не указано'}\n\n"
            f"Используйте /profile для просмотра данных\n"
            f"/help — справка по командам",
            reply_markup=get_main_keyboard(),
            parse_mode="HTML"
        )
    else:
        await message.answer("❌ Ошибка сохранения. Возможно, вы уже зарегистрированы.")
    
    await state.clear()

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
    
    # ВЛК статус
    vlk_status = ""
    if medical and medical[1]:
        status = check_vlk_status(medical[1])
        if status['vlk_expired']:
            vlk_status = f"🔴 <b>ВЛК:</b> ИСТЁКЛА! ({status['days_passed']} дн. назад)\n<i>Полёты ЗАПРЕЩЕНЫ!</i>"
        elif status['umo_needed'] and not medical[2]:
            vlk_status = f"🟠 <b>ВЛК:</b> Требуется УМО! ({status['days_passed']} дн. с ВЛК)"
        elif status['remind_7']:
            vlk_status = f"🔴 <b>ВЛК:</b> Истекает через {status['days_remaining']} дн.!"
        elif status['remind_15']:
            vlk_status = f"🟠 <b>ВЛК:</b> Истекает через {status['days_remaining']} дн."
        elif status['remind_30']:
            vlk_status = f"🟡 <b>ВЛК:</b> Истекает через {status['days_remaining']} дн."
        else:
            vlk_status = f"🟢 <b>ВЛК:</b> Действует ({status['days_remaining']} дн.)"
    
    # УМО статус
    umo_status = ""
    if medical and medical[2]:
        umo_date = datetime.strptime(medical[2], "%Y-%m-%d")
        umo_status = f"🟢 <b>УМО:</b> Пройдено ({medical[2]})"
    elif medical and medical[1]:
        status = check_vlk_status(medical[1])
        if status['umo_needed']:
            umo_status = f"🔴 <b>УМО:</b> НЕ ПРОЙДЕНО!"
    
    # КБП статус
    check_status = ""
    if checks:
        if checks[1]:
            ex4 = check_exercise_status(checks[1], 6)
            if ex4['expired']:
                check_status += f"🔴 <b>Упр.4:</b> ИСТЕКЛО! ({abs(ex4['days_remaining'])} дн. назад)\n"
            elif ex4['days_remaining'] <= 30:
                check_status += f"🟠 <b>Упр.4:</b> {ex4['days_remaining']} дн. (до {ex4['valid_until']})\n"
            else:
                check_status += f"🟢 <b>Упр.4:</b> {ex4['days_remaining']} дн. (до {ex4['valid_until']})\n"
        
        if checks[2]:
            ex7 = check_exercise_status(checks[2], 12)
            if ex7['expired']:
                check_status += f"🔴 <b>Упр.7:</b> ИСТЕКЛО! ({abs(ex7['days_remaining'])} дн. назад)\n"
            elif ex7['days_remaining'] <= 30:
                check_status += f"🟠 <b>Упр.7:</b> {ex7['days_remaining']} дн. (до {ex7['valid_until']})\n"
            else:
                check_status += f"🟢 <b>Упр.7:</b> {ex7['days_remaining']} дн. (до {ex7['valid_until']})\n"
    
    # Отпуск статус
    vac_status = ""
    if vacation and vacation[2]:
        vac = check_vacation_status(vacation[2])
        vac_days = vacation[3] if len(vacation) > 3 else 0
        if vac['expired']:
            vac_status = f"🔴 <b>Отпуск:</b> Истёк! ({vac['days_passed']} дн. назад)\n<i>Дней было: {vac_days}</i>"
        elif vac['remind_7']:
            vac_status = f"🔴 <b>Отпуск:</b> Через {vac['days_until_next']} дн. нужен новый!\n<i>Дней было: {vac_days}</i>"
        elif vac['remind_15']:
            vac_status = f"🟠 <b>Отпуск:</b> Через {vac['days_until_next']} дн. нужен новый\n<i>Дней было: {vac_days}</i>"
        elif vac['remind_30']:
            vac_status = f"🟡 <b>Отпуск:</b> Через {vac['days_until_next']} дн. нужен новый\n<i>Дней было: {vac_days}</i>"
        else:
            vac_status = f"🟢 <b>Отпуск:</b> Действует (осталось {vac['days_until_next']} дн.)\n<i>Дней было: {vac_days}</i>"
    
    full_name = f"{user[1]} {user[2]}"
    if user[3]:
        full_name += f" {user[3]}"
    
    await message.answer(
        f"📋 <b>ВАШИ ДАННЫЕ:</b>\n\n"
        f"👤 <b>ФИО:</b> {full_name}\n"
        f"🎖️ <b>Звание:</b> {user[4] or 'не указано'}\n\n"
        f"{vlk_status}\n"
        f"{umo_status}\n"
        f"{check_status}"
        f"{vac_status}",
        parse_mode="HTML",
        reply_markup=get_main_keyboard()
    )

# ==================== /all (АДМИН - ПОЛНЫЕ ДАННЫЕ) ====================

@dp.message(Command("all"))
async def cmd_all(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("❌ Доступ только для администратора.")
        return
    
    users = get_all_users()
    
    if not users:
        await message.answer("📭 В базе данных нет пользователей.")
        return
    
    report = f"👥 <b>ВСЕ ПОЛЬЗОВАТЕЛИ ({len(users)} чел.)</b>\n\n"
    
    for i, user in enumerate(users, 1):
        telegram_id = user[0]
        surname = user[1]
        name = user[2]
        rank = user[3] or "не указано"
        
        full_name = f"{surname} {name}"
        
        # Получаем дополнительные данные
        medical = get_medical(telegram_id)
        checks = get_checks(telegram_id)
        vacation = get_vacation(telegram_id)
        
        report += f"<b>#{i}. {full_name}</b> ({rank})\n"
        report += f"   ID: <code>{telegram_id}</code>\n"
        
        # ВЛК
        if medical and medical[1]:
            vlk = check_vlk_status(medical[1])
            if vlk['vlk_expired']:
                report += f"   🔴 <b>ВЛК:</b> ИСТЕКЛА! ({vlk['days_passed']} дн. назад)\n"
            elif vlk['umo_needed'] and not medical[2]:
                report += f"   🟠 <b>ВЛК:</b> Нужно УМО! ({vlk['days_passed']} дн.)\n"
            else:
                report += f"   🟢 <b>ВЛК:</b> {vlk['days_remaining']} дн.\n"
            
            # УМО
            if medical[2]:
                report += f"   🟢 <b>УМО:</b> {medical[2]}\n"
            elif vlk['umo_needed']:
                report += f"   🔴 <b>УМО:</b> НЕ ПРОЙДЕНО!\n"
        else:
            report += f"   ⚪ <b>ВЛК:</b> нет данных\n"
        
        # КБП
        if checks:
            if checks[1]:
                ex4 = check_exercise_status(checks[1], 6)
                if ex4['expired']:
                    report += f"   🔴 <b>Упр.4:</b> ИСТЕКЛО! ({abs(ex4['days_remaining'])} дн.)\n"
                else:
                    report += f"   🟢 <b>Упр.4:</b> {ex4['days_remaining']} дн.\n"
            if checks[2]:
                ex7 = check_exercise_status(checks[2], 12)
                if ex7['expired']:
                    report += f"   🔴 <b>Упр.7:</b> ИСТЕКЛО! ({abs(ex7['days_remaining'])} дн.)\n"
                else:
                    report += f"   🟢 <b>Упр.7:</b> {ex7['days_remaining']} дн.\n"
        else:
            report += f"   ⚪ <b>КБП:</b> нет данных\n"
        
        # Отпуск
        if vacation and vacation[2]:
            vac = check_vacation_status(vacation[2])
            vac_days = vacation[3] if len(vacation) > 3 else 0
            if vac['expired']:
                report += f"   🔴 <b>Отпуск:</b> ИСТЁК! ({vac_days} дн., {vac['days_passed']} дн. назад)\n"
            else:
                report += f"   🟢 <b>Отпуск:</b> {vac_days} дн. (осталось {vac['days_until_next']} дн.)\n"
        else:
            report += f"   ⚪ <b>Отпуск:</b> нет данных\n"
        
        report += "\n"
        
        # Разделяем длинные сообщения
        if len(report) > 3000:
            await message.answer(report, parse_mode="HTML")
            report = ""
    
    if report:
        await message.answer(report, parse_mode="HTML")

# ==================== /delete ====================

@dp.message(Command("delete"))
async def cmd_delete(message: types.Message, state: FSMContext):
    user = get_user(message.from_user.id)
    
    if not user:
        await message.answer("❌ У вас нет данных для удаления.")
        return
    
    await message.answer(
        "⚠️ <b>ВНИМАНИЕ!</b>\n\n"
        "Вы действительно хотите удалить ВСЕ свои данные?\n"
        "Это действие НЕЛЬЗЯ отменить!\n\n"
        "Напишите <b>ДА</b> для подтверждения или <b>НЕТ</b> для отмены:",
        parse_mode="HTML"
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
        "✏️ <b>Редактирование данных</b>\n\n"
        "Что вы хотите изменить?\n\n"
        "1 — Фамилия\n"
        "2 — Имя\n"
        "3 — Отчество\n"
        "4 — Звание\n"
        "0 — Отмена",
        parse_mode="HTML"
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
    await message.answer(f"Введите новое значение для поля <b>{field_name[field]}</b>:", parse_mode="HTML")
    await state.set_state(Form.update_value)

@dp.message(Form.update_value)
async def process_update_value(message: types.Message, state: FSMContext):
    data = await state.get_data()
    field = data.get('update_field')
    update_user(message.from_user.id, **{field: message.text})
    await message.answer(f"✅ Поле <b>{field}</b> обновлено на: {message.text}", parse_mode="HTML")
    await state.clear()

# ==================== /vlk ====================

@dp.message(Command("vlk"))
async def cmd_vlk(message: types.Message, state: FSMContext):
    await message.answer(
        "🏥 <b>ВЛК</b>\n\n"
        "Введите дату прохождения ВЛК в формате <b>ГГГГ-ММ-ДД</b>:\n"
        "Пример: 2025-02-19",
        parse_mode="HTML"
    )
    await state.set_state(Form.vlk_date)

@dp.message(Form.vlk_date)
async def process_vlk_date(message: types.Message, state: FSMContext):
    try:
        datetime.strptime(message.text, "%Y-%m-%d")
        add_medical(message.from_user.id, message.text)
        await message.answer(f"✅ <b>ВЛК сохранена:</b> {message.text}", parse_mode="HTML")
        
        # Уведомление админу
        user = get_user(message.from_user.id)
        if user:
            full_name = f"{user[1]} {user[2]}"
            await bot.send_message(
                ADMIN_ID,
                f"📝 <b>Пользователь обновил ВЛК</b>\n\n"
                f"👤 {full_name}\n"
                f"🆔 ID: <code>{message.from_user.id}</code>\n"
                f"📅 Дата ВЛК: {message.text}",
                parse_mode="HTML"
            )
    except ValueError:
        await message.answer("❌ Неверный формат. Используйте ГГГГ-ММ-ДД:")
        return
    await state.clear()

# ==================== /checks ====================

@dp.message(Command("checks"))
async def cmd_checks(message: types.Message, state: FSMContext):
    await message.answer(
        "✈️ <b>Проверки КБП</b>\n\n"
        "Какое упражнение добавить?\n"
        "4 — Упражнение 4 (6 месяцев)\n"
        "7 — Упражнение 7 (12 месяцев)\n"
        "0 — Отмена",
        parse_mode="HTML"
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
    await message.answer("Введите дату проверки в формате <b>ГГГГ-ММ-ДД</b>:", parse_mode="HTML")
    await state.set_state(Form.exercise_7_date)

@dp.message(Form.exercise_7_date)
async def process_exercise_date(message: types.Message, state: FSMContext):
    try:
        data = await state.get_data()
        exercise = data.get('exercise_num')
        datetime.strptime(message.text, "%Y-%m-%d")
        add_check(message.from_user.id, exercise, message.text)
        await message.answer(f"✅ <b>Упражнение {exercise} сохранено:</b> {message.text}", parse_mode="HTML")
        
        # Уведомление админу
        user = get_user(message.from_user.id)
        if user:
            full_name = f"{user[1]} {user[2]}"
            await bot.send_message(
                ADMIN_ID,
                f"📝 <b>Пользователь обновил проверку</b>\n\n"
                f"👤 {full_name}\n"
                f"🆔 ID: <code>{message.from_user.id}</code>\n"
                f"✈️ Упражнение {exercise}: {message.text}",
                parse_mode="HTML"
            )
    except ValueError:
        await message.answer("❌ Неверный формат. Используйте ГГГГ-ММ-ДД:")
        return
    await state.clear()

# ==================== /vacation ====================

@dp.message(Command("vacation"))
async def cmd_vacation(message: types.Message, state: FSMContext):
    await message.answer(
        "🏖️ <b>Отпуск</b>\n\n"
        "Введите дату <b>начала</b> отпуска (ГГГГ-ММ-ДД):",
        parse_mode="HTML"
    )
    await state.set_state(Form.vacation_start)

@dp.message(Form.vacation_start)
async def process_vacation_start(message: types.Message, state: FSMContext):
    try:
        datetime.strptime(message.text, "%Y-%m-%d")
        await state.update_data(vac_start=message.text)
        await message.answer("Введите дату <b>окончания</b> отпуска (ГГГГ-ММ-ДД):", parse_mode="HTML")
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
        
        # Считаем дни
        start = datetime.strptime(data['vac_start'], "%Y-%m-%d")
        end = datetime.strptime(message.text, "%Y-%m-%d")
        days = (end - start).days + 1
        
        await message.answer(
            f"✅ <b>Отпуск сохранён!</b>\n\n"
            f"📅 {data['vac_start']} — {message.text}\n"
            f"📊 Дней: {days}",
            parse_mode="HTML"
        )
        
        # Уведомление админу
        user = get_user(message.from_user.id)
        if user:
            full_name = f"{user[1]} {user[2]}"
            await bot.send_message(
                ADMIN_ID,
                f"📝 <b>Пользователь обновил отпуск</b>\n\n"
                f"👤 {full_name}\n"
                f"🆔 ID: <code>{message.from_user.id}</code>\n"
                f"📅 {data['vac_start']} — {message.text} ({days} дн.)",
                parse_mode="HTML"
            )
    except ValueError:
        await message.answer("❌ Неверный формат. Используйте ГГГГ-ММ-ДД:")
        return
    await state.clear()

# ==================== ОБРАБОТКА КНОПОК ====================

@dp.callback_query(lambda c: c.data == "profile")
async def process_profile_callback(callback_query: types.CallbackQuery):
    """Обработка кнопки профиля"""
    logger.info(f"Callback profile от {callback_query.from_user.id}")
    await callback_query.answer()
    
    user = get_user(callback_query.from_user.id)
    if not user:
        await callback_query.message.answer("❌ Вы ещё не зарегистрированы. Используйте /start")
        return
    
    medical = get_medical(callback_query.from_user.id)
    checks = get_checks(callback_query.from_user.id)
    
    vlk_status = ""
    if medical and medical[1]:
        status = check_vlk_status(medical[1])
        if status['vlk_expired']:
            vlk_status = "🔴 <b>ВЛК:</b> ИСТЁКЛА!"
        elif status['umo_needed'] and not medical[2]:
            vlk_status = "🟠 <b>ВЛК:</b> Требуется УМО!"
        else:
            vlk_status = f"🟢 <b>ВЛК:</b> {status['days_remaining']} дн."
    
    full_name = f"{user[1]} {user[2]}"
    if user[3]:
        full_name += f" {user[3]}"
    
    await callback_query.message.answer(
        f"📋 <b>{full_name}</b>\n\n"
        f"🎖️ {user[4] or 'не указано'}\n\n"
        f"{vlk_status}",
        reply_markup=get_main_keyboard(),
        parse_mode="HTML"
    )

@dp.callback_query(lambda c: c.data == "help")
async def process_help_callback(callback_query: types.CallbackQuery):
    """Обработка кнопки помощи"""
    logger.info(f"Callback help от {callback_query.from_user.id}")
    await callback_query.answer()
    await callback_query.message.answer(
        "📖 <b>Доступные команды:</b>\n\n"
        "/start — Регистрация\n"
        "/profile — Мои данные\n"
        "/vlk — Добавить ВЛК\n"
        "/checks — Добавить проверки\n"
        "/vacation — Добавить отпуск\n"
        "/update — Редактировать\n"
        "/delete — Удалить данные\n"
        "/all — Список пользователей (админ)",
        reply_markup=get_main_keyboard(),
        parse_mode="HTML"
    )

@dp.callback_query(lambda c: c.data == "vlk")
async def process_vlk_callback(callback_query: types.CallbackQuery):
    """Обработка кнопки ВЛК"""
    logger.info(f"Callback vlk от {callback_query.from_user.id}")
    await callback_query.answer()
    await callback_query.message.answer(
        "🏥 <b>ВЛК</b>\n\n"
        "Используйте команду /vlk для добавления даты ВЛК",
        parse_mode="HTML"
    )

@dp.callback_query(lambda c: c.data == "checks")
async def process_checks_callback(callback_query: types.CallbackQuery):
    """Обработка кнопки проверок"""
    logger.info(f"Callback checks от {callback_query.from_user.id}")
    await callback_query.answer()
    await callback_query.message.answer(
        "✈️ <b>Проверки КБП</b>\n\n"
        "Используйте команду /checks для добавления проверок",
        parse_mode="HTML"
    )

@dp.callback_query(lambda c: c.data == "vacation")
async def process_vacation_callback(callback_query: types.CallbackQuery):
    """Обработка кнопки отпуска"""
    logger.info(f"Callback vacation от {callback_query.from_user.id}")
    await callback_query.answer()
    await callback_query.message.answer(
        "🏖️ <b>Отпуск</b>\n\n"
        "Используйте команду /vacation для добавления отпуска",
        parse_mode="HTML"
    )

@dp.callback_query(lambda c: c.data == "update")
async def process_update_callback(callback_query: types.CallbackQuery):
    """Обработка кнопки редактирования"""
    logger.info(f"Callback update от {callback_query.from_user.id}")
    await callback_query.answer()
    await callback_query.message.answer(
        "✏️ <b>Редактирование</b>\n\n"
        "Используйте команду /update",
        parse_mode="HTML"
    )

@dp.callback_query(lambda c: c.data == "delete")
async def process_delete_callback(callback_query: types.CallbackQuery):
    """Обработка кнопки удаления"""
    logger.info(f"Callback delete от {callback_query.from_user.id}")
    await callback_query.answer()
    await callback_query.message.answer(
        "🗑️ <b>Удаление данных</b>\n\n"
        "Используйте команду /delete",
        parse_mode="HTML"
    )

@dp.callback_query(lambda c: c.data == "start_reg")
async def process_start_reg_callback(callback_query: types.CallbackQuery):
    """Обработка кнопки регистрации"""
    logger.info(f"Callback start_reg от {callback_query.from_user.id}")
    await callback_query.answer()
    await callback_query.message.answer(
        "👋 <b>Регистрация</b>\n\n"
        "Используйте команду /start",
        parse_mode="HTML"
    )

# ==================== ОБРАБОТКА УПОМИНАНИЙ В ГРУППЕ ====================

@dp.message()
async def handle_mention(message: types.Message):
    """Отвечает когда бота упоминают в группе"""
    
    if message.text and message.text.startswith('/'):
        return
    
    if message.chat.type not in ["group", "supergroup"]:
        return
    
    if message.entities:
        for entity in message.entities:
            if entity.type == "mention":
                mention = message.text[entity.offset:entity.offset+entity.length]
                if mention.lower() == f"@{bot.username.lower()}":
                    await message.answer(
                        f"👋 {message.from_user.first_name}!\n\n"
                        f"Я здесь! Используйте /menu для команд.",
                        reply_markup=get_group_help_keyboard(),
                        parse_mode="HTML"
                    )
                    return

# ==================== ВЕБ-СЕРВЕР ====================

app = web.Application()
SimpleRequestHandler(dispatcher=dp, bot=bot).register(app, path="/webhook")
setup_application(app, dp, bot=bot)

async def on_startup(app: web.Application):
    """Запуск бота: webhook + планировщик"""
    init_db()
    await bot.set_webhook(WEBHOOK_URL)
    asyncio.create_task(run_scheduler(bot, interval_hours=24))
    logger.info("Планировщик напоминаний запущен!")

async def on_shutdown(app: web.Application):
    """Остановка бота"""
    await bot.delete_webhook()

app.on_startup.append(on_startup)
app.on_shutdown.append(on_shutdown)

if __name__ == "__main__":
    web.run_app(app, host="0.0.0.0", port=PORT)

