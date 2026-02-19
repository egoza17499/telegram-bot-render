import asyncio
import logging
from datetime import datetime
from aiogram import Bot

from database import (
    get_all_users, get_medical, get_checks, get_vacation,
    check_vlk_status, check_exercise_status, check_vacation_status
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ID админа
ADMIN_ID = 393293807

async def send_daily_reminders(bot: Bot):
    """Ежедневная рассылка напоминаний"""
    logger.info("Запуск проверки напоминаний...")
    
    users = get_all_users()
    
    if not users:
        logger.info("Пользователей в базе нет")
        return
    
    for user in users:
        telegram_id = user[0]
        surname = user[1]
        name = user[2]
        rank = user[3] if len(user) > 3 else ""
        full_name = f"{surname} {name}"
        
        try:
            # ===== ПРОВЕРКА ВЛК =====
            medical = get_medical(telegram_id)
            if medical and medical[1]:
                vlk_date = medical[1]
                umo_date = medical[2]
                status = check_vlk_status(vlk_date)
                
                # Формируем сообщение для пользователя
                user_msg = ""
                admin_msg = f"📊 <b>Напоминание: {full_name}</b> (ID: {telegram_id})\n\n"
                
                if status['vlk_expired']:
                    user_msg = (
                        f"⛔ <b>СРОЧНО! ВЛК ИСТЕКЛА!</b>\n\n"
                        f"У вас истёк срок действия ВЛК!\n"
                        f"📅 Прошло дней: {status['days_passed']}\n\n"
                        f"❌ <b>ПОЛЁТЫ ЗАПРЕЩЕНЫ!</b>"
                    )
                    admin_msg += f"🔴 <b>ВЛК:</b> ИСТЕКЛА! ({status['days_passed']} дн. назад)\n"
                    admin_msg += f"❌ ПОЛЁТЫ ЗАПРЕЩЕНЫ!"
                
                elif status['umo_needed'] and not umo_date:
                    user_msg = (
                        f"⚠️ <b>ТРЕБУЕТСЯ УМО!</b>\n\n"
                        f"Прошло более 6 месяцев с ВЛК.\n"
                        f"📅 Дата ВЛК: {vlk_date}\n\n"
                        f"Необходимо пройти УМО для продления ВЛК!"
                    )
                    admin_msg += f"🟠 <b>ВЛК:</b> Требуется УМО! ({status['days_passed']} дн.)"
                
                elif status['remind_30']:
                    user_msg = (
                        f"⏰ <b>ВЛК истекает через 30 дней!</b>\n\n"
                        f"Напоминаем о необходимости пройти ВЛК.\n"
                        f"📅 Осталось дней: {status['days_remaining']}"
                    )
                    admin_msg += f"🟡 <b>ВЛК:</b> Через {status['days_remaining']} дн."
                
                elif status['remind_15']:
                    user_msg = (
                        f"⏰ <b>ВЛК истекает через 15 дней!</b>\n\n"
                        f"Осталось мало времени.\n"
                        f"📅 Осталось дней: {status['days_remaining']}"
                    )
                    admin_msg += f"🟠 <b>ВЛК:</b> Через {status['days_remaining']} дн.!"
                
                elif status['remind_7']:
                    user_msg = (
                        f"🚨 <b>ВЛК истекает через 7 дней!</b>\n\n"
                        f"СРОЧНО пройдите ВЛК!\n"
                        f"📅 Осталось дней: {status['days_remaining']}"
                    )
                    admin_msg += f"🔴 <b>ВЛК:</b> Через {status['days_remaining']} дн.!!"
                
                # Отправляем сообщения
                if user_msg:
                    try:
                        await bot.send_message(telegram_id, user_msg, parse_mode="HTML")
                    except Exception as e:
                        logger.error(f"Не удалось отправить пользователю {telegram_id}: {e}")
                
                if admin_msg and not admin_msg.endswith("нет"):
                    try:
                        await bot.send_message(ADMIN_ID, admin_msg, parse_mode="HTML")
                    except Exception as e:
                        logger.error(f"Не удалось отправить админу: {e}")
            
            # ===== ПРОВЕРКА КБП =====
            checks = get_checks(telegram_id)
            if checks:
                # Упражнение 4 (6 месяцев)
                if checks[1]:
                    ex4_status = check_exercise_status(checks[1], 6)
                    
                    if ex4_status['expired']:
                        user_msg = (
                            f"⛔ <b>Упражнение 4 ИСТЕКЛО!</b>\n\n"
                            f"Срок действия упражнения 4 истёк.\n"
                            f"📅 Истекло дней назад: {abs(ex4_status['days_remaining'])}\n\n"
                            f"❌ <b>ПОЛЁТЫ ЗАПРЕЩЕНЫ!</b>"
                        )
                        admin_msg = (
                            f"📊 <b>Напоминание: {full_name}</b> (ID: {telegram_id})\n\n"
                            f"🔴 <b>Упр.4:</b> ИСТЕКЛО! ({abs(ex4_status['days_remaining'])} дн. назад)\n"
                            f"❌ ПОЛЁТЫ ЗАПРЕЩЕНЫ!"
                        )
                        try:
                            await bot.send_message(telegram_id, user_msg, parse_mode="HTML")
                            await bot.send_message(ADMIN_ID, admin_msg, parse_mode="HTML")
                        except Exception as e:
                            logger.error(f"Ошибка отправки Упр.4: {e}")
                    
                    elif ex4_status['days_remaining'] <= 30:
                        user_msg = (
                            f"⏰ <b>Упражнение 4 истекает!</b>\n\n"
                            f"Осталось {ex4_status['days_remaining']} дн.\n"
                            f"📅 Действительно до: {ex4_status['valid_until']}"
                        )
                        admin_msg = (
                            f"📊 <b>Напоминание: {full_name}</b> (ID: {telegram_id})\n\n"
                            f"🟡 <b>Упр.4:</b> Через {ex4_status['days_remaining']} дн."
                        )
                        try:
                            await bot.send_message(telegram_id, user_msg, parse_mode="HTML")
                            await bot.send_message(ADMIN_ID, admin_msg, parse_mode="HTML")
                        except Exception as e:
                            logger.error(f"Ошибка отправки Упр.4: {e}")
                
                # Упражнение 7 (12 месяцев)
                if checks[2]:
                    ex7_status = check_exercise_status(checks[2], 12)
                    
                    if ex7_status['expired']:
                        user_msg = (
                            f"⛔ <b>Упражнение 7 ИСТЕКЛО!</b>\n\n"
                            f"Срок действия упражнения 7 истёк.\n"
                            f"📅 Истекло дней назад: {abs(ex7_status['days_remaining'])}\n\n"
                            f"❌ <b>ПОЛЁТЫ ЗАПРЕЩЕНЫ!</b>"
                        )
                        admin_msg = (
                            f"📊 <b>Напоминание: {full_name}</b> (ID: {telegram_id})\n\n"
                            f"🔴 <b>Упр.7:</b> ИСТЕКЛО! ({abs(ex7_status['days_remaining'])} дн. назад)\n"
                            f"❌ ПОЛЁТЫ ЗАПРЕЩЕНЫ!"
                        )
                        try:
                            await bot.send_message(telegram_id, user_msg, parse_mode="HTML")
                            await bot.send_message(ADMIN_ID, admin_msg, parse_mode="HTML")
                        except Exception as e:
                            logger.error(f"Ошибка отправки Упр.7: {e}")
                    
                    elif ex7_status['days_remaining'] <= 30:
                        user_msg = (
                            f"⏰ <b>Упражнение 7 истекает!</b>\n\n"
                            f"Осталось {ex7_status['days_remaining']} дн.\n"
                            f"📅 Действительно до: {ex7_status['valid_until']}"
                        )
                        admin_msg = (
                            f"📊 <b>Напоминание: {full_name}</b> (ID: {telegram_id})\n\n"
                            f"🟡 <b>Упр.7:</b> Через {ex7_status['days_remaining']} дн."
                        )
                        try:
                            await bot.send_message(telegram_id, user_msg, parse_mode="HTML")
                            await bot.send_message(ADMIN_ID, admin_msg, parse_mode="HTML")
                        except Exception as e:
                            logger.error(f"Ошибка отправки Упр.7: {e}")
            
            # ===== ПРОВЕРКА ОТПУСКА =====
            vacation = get_vacation(telegram_id)
            if vacation and vacation[2]:
                vac_status = check_vacation_status(vacation[2])
                vac_days = vacation[3] if len(vacation) > 3 else 0
                
                if vac_status['expired']:
                    user_msg = (
                        f"⚠️ <b>Отпуск истёк!</b>\n\n"
                        f"С момента окончания отпуска прошло больше года.\n"
                        f"📅 Прошло дней: {vac_status['days_passed']}\n"
                        f"📊 Дней отпуска было: {vac_days}\n\n"
                        f"Необходимо оформить новый отпуск!"
                    )
                    admin_msg = (
                        f"📊 <b>Напоминание: {full_name}</b> (ID: {telegram_id})\n\n"
                        f"🔴 <b>Отпуск:</b> ИСТЁК! ({vac_days} дн., {vac_status['days_passed']} дн. назад)"
                    )
                    try:
                        await bot.send_message(telegram_id, user_msg, parse_mode="HTML")
                        await bot.send_message(ADMIN_ID, admin_msg, parse_mode="HTML")
                    except Exception as e:
                        logger.error(f"Ошибка отправки отпуск: {e}")
                
                elif vac_status['remind_30']:
                    user_msg = (
                        f"⏰ <b>До отпуска 30 дней!</b>\n\n"
                        f"Через {vac_status['days_until_next']} дн. нужен новый отпуск.\n"
                        f"📊 Прошлый отпуск: {vac_days} дн."
                    )
                    admin_msg = (
                        f"📊 <b>Напоминание: {full_name}</b> (ID: {telegram_id})\n\n"
                        f"🟡 <b>Отпуск:</b> Через {vac_status['days_until_next']} дн."
                    )
                    try:
                        await bot.send_message(telegram_id, user_msg, parse_mode="HTML")
                        await bot.send_message(ADMIN_ID, admin_msg, parse_mode="HTML")
                    except Exception as e:
                        logger.error(f"Ошибка отправки отпуск: {e}")
                
                elif vac_status['remind_15']:
                    user_msg = (
                        f"⏰ <b>До отпуска 15 дней!</b>\n\n"
                        f"Через {vac_status['days_until_next']} дн. нужен новый отпуск."
                    )
                    admin_msg = (
                        f"📊 <b>Напоминание: {full_name}</b> (ID: {telegram_id})\n\n"
                        f"🟠 <b>Отпуск:</b> Через {vac_status['days_until_next']} дн.!"
                    )
                    try:
                        await bot.send_message(telegram_id, user_msg, parse_mode="HTML")
                        await bot.send_message(ADMIN_ID, admin_msg, parse_mode="HTML")
                    except Exception as e:
                        logger.error(f"Ошибка отправки отпуск: {e}")
                
                elif vac_status['remind_7']:
                    user_msg = (
                        f"🚨 <b>До отпуска 7 дней!</b>\n\n"
                        f"Через {vac_status['days_until_next']} дн. нужен новый отпуск."
                    )
                    admin_msg = (
                        f"📊 <b>Напоминание: {full_name}</b> (ID: {telegram_id})\n\n"
                        f"🔴 <b>Отпуск:</b> Через {vac_status['days_until_next']} дн.!!"
                    )
                    try:
                        await bot.send_message(telegram_id, user_msg, parse_mode="HTML")
                        await bot.send_message(ADMIN_ID, admin_msg, parse_mode="HTML")
                    except Exception as e:
                        logger.error(f"Ошибка отправки отпуск: {e}")
        
        except Exception as e:
            logger.error(f"Ошибка при проверке пользователя {telegram_id}: {e}")
    
    logger.info("Проверка напоминаний завершена")

async def run_scheduler(bot: Bot, interval_hours: int = 24):
    """Запуск планировщика"""
    while True:
        try:
            await send_daily_reminders(bot)
            await asyncio.sleep(interval_hours * 3600)
        except Exception as e:
            logger.error(f"Ошибка в планировщике: {e}")
            await asyncio.sleep(3600)
