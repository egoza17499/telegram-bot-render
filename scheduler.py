import asyncio
import logging
from datetime import datetime
from aiogram import Bot

# Импортируем функции из database
from database import (
    get_all_users, get_medical, get_checks, get_vacation,
    check_vlk_status, check_exercise_status, check_vacation_status
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ID админа для отчётов
ADMIN_ID = 393293807  # Твой ID

async def send_daily_reminders(bot: Bot):
    """Ежедневная рассылка напоминаний АДМИНУ"""
    logger.info("Запуск проверки напоминаний...")
    
    users = get_all_users()
    
    if not users:
        logger.info("Пользователей в базе нет")
        return
    
    # Списки для отчёта
    vlk_expired = []
    vlk_30_days = []
    vlk_15_days = []
    vlk_7_days = []
    umo_needed = []
    ex4_expired = []
    ex4_30_days = []
    ex7_expired = []
    ex7_30_days = []
    vacation_expired = []
    vacation_30_days = []
    vacation_15_days = []
    vacation_7_days = []
    
    for user in users:
        telegram_id = user[0]
        surname = user[1]
        name = user[2]
        rank = user[3] if len(user) > 3 else ""
        full_name = f"{surname} {name}"
        
        try:
            # ===== ПРОВЕРКА ВЛК =====
            medical = get_medical(telegram_id)
            if medical and medical[1]:  # vlk_date
                vlk_date = medical[1]
                umo_date = medical[2]
                status = check_vlk_status(vlk_date)
                
                if status['vlk_expired']:
                    vlk_expired.append(f"{full_name} — ВЛК истекла ({status['days_passed']} дн. назад)")
                
                elif status['umo_needed'] and not umo_date:
                    umo_needed.append(f"{full_name} — требуется УМО (ВЛК от {vlk_date})")
                
                elif status['remind_30']:
                    vlk_30_days.append(f"{full_name} — {status['days_remaining']} дн.")
                
                elif status['remind_15']:
                    vlk_15_days.append(f"{full_name} — {status['days_remaining']} дн.")
                
                elif status['remind_7']:
                    vlk_7_days.append(f"{full_name} — {status['days_remaining']} дн.")
            
            # ===== ПРОВЕРКА КБП =====
            checks = get_checks(telegram_id)
            if checks:
                # Упражнение 4 (6 месяцев)
                if checks[1]:
                    ex4_status = check_exercise_status(checks[1], 6)
                    
                    if ex4_status['expired']:
                        ex4_expired.append(f"{full_name} — истекло ({abs(ex4_status['days_remaining'])} дн. назад)")
                    
                    elif ex4_status['remind_30']:
                        ex4_30_days.append(f"{full_name} — {ex4_status['days_remaining']} дн.")
                
                # Упражнение 7 (12 месяцев)
                if checks[2]:
                    ex7_status = check_exercise_status(checks[2], 12)
                    
                    if ex7_status['expired']:
                        ex7_expired.append(f"{full_name} — истекло ({abs(ex7_status['days_remaining'])} дн. назад)")
                    
                    elif ex7_status['remind_30']:
                        ex7_30_days.append(f"{full_name} — {ex7_status['days_remaining']} дн.")
            
            # ===== ПРОВЕРКА ОТПУСКА =====
            vacation = get_vacation(telegram_id)
            if vacation and vacation[2]:
                vac_status = check_vacation_status(vacation[2])
                
                if vac_status['expired']:
                    vacation_expired.append(f"{full_name} — истёк ({vac_status['days_passed']} дн. назад)")
                
                elif vac_status['remind_30']:
                    vacation_30_days.append(f"{full_name} — {vac_status['days_until_next']} дн.")
                
                elif vac_status['remind_15']:
                    vacation_15_days.append(f"{full_name} — {vac_status['days_until_next']} дн.")
                
                elif vac_status['remind_7']:
                    vacation_7_days.append(f"{full_name} — {vac_status['days_until_next']} дн.")
        
        except Exception as e:
            logger.error(f"Ошибка при проверке пользователя {telegram_id}: {e}")
    
    # ===== ФОРМИРУЕМ ОТЧЁТ ДЛЯ АДМИНА =====
    report = "📊 **ЕЖЕДНЕВНЫЙ ОТЧЁТ**\n"
    report += f"📅 {datetime.now().strftime('%d.%m.%Y %H:%M')}\n\n"
    
    # СРОЧНЫЕ (истекло)
    if vlk_expired:
        report += "⛔ **ВЛК ИСТЕКЛА:**\n" + "\n".join(vlk_expired) + "\n\n"
    
    if ex4_expired:
        report += "⛔ **Упр.4 ИСТЕКЛО:**\n" + "\n".join(ex4_expired) + "\n\n"
    
    if ex7_expired:
        report += "⛔ **Упр.7 ИСТЕКЛО:**\n" + "\n".join(ex7_expired) + "\n\n"
    
    if vacation_expired:
        report += "⚠️ **ОТПУСК ИСТЁК:**\n" + "\n".join(vacation_expired) + "\n\n"
    
    # ВНИМАНИЕ (требуется действие)
    if umo_needed:
        report += "⚠️ **ТРЕБУЕТСЯ УМО:**\n" + "\n".join(umo_needed) + "\n\n"
    
    # НАПОМИНАНИЯ (30 дней)
    if vlk_30_days:
        report += "⏰ **ВЛК через 30 дней:**\n" + "\n".join(vlk_30_days) + "\n\n"
    
    if vlk_15_days:
        report += "⏰ **ВЛК через 15 дней:**\n" + "\n".join(vlk_15_days) + "\n\n"
    
    if vlk_7_days:
        report += "🚨 **ВЛК через 7 дней:**\n" + "\n".join(vlk_7_days) + "\n\n"
    
    if ex4_30_days:
        report += "⏰ **Упр.4 через 30 дней:**\n" + "\n".join(ex4_30_days) + "\n\n"
    
    if ex7_30_days:
        report += "⏰ **Упр.7 через 30 дней:**\n" + "\n".join(ex7_30_days) + "\n\n"
    
    if vacation_30_days:
        report += "⏰ **Отпуск через 30 дней:**\n" + "\n".join(vacation_30_days) + "\n\n"
    
    if vacation_15_days:
        report += "⏰ **Отпуск через 15 дней:**\n" + "\n".join(vacation_15_days) + "\n\n"
    
    if vacation_7_days:
        report += "🚨 **Отпуск через 7 дней:**\n" + "\n".join(vacation_7_days) + "\n\n"
    
    # Если ничего нет
    if len(report.split("\n")) == 3:
        report += "✅ Всё в порядке! Напоминаний нет."
    
    # Отправляем отчёт админу
    try:
        await bot.send_message(ADMIN_ID, report, parse_mode="Markdown")
        logger.info(f"Отчёт отправлен админу {ADMIN_ID}")
    except Exception as e:
        logger.error(f"Не удалось отправить отчёт админу: {e}")

async def run_scheduler(bot: Bot, interval_hours: int = 24):
    """Запуск планировщика"""
    while True:
        try:
            await send_daily_reminders(bot)
            await asyncio.sleep(interval_hours * 3600)
        except Exception as e:
            logger.error(f"Ошибка в планировщике: {e}")
            await asyncio.sleep(3600)