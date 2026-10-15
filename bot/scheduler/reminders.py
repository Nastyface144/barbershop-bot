"""Напоминания клиентам за 24 и за 2 часа до визита.

Раз в минуту планировщик проверяет ближайшие записи. Отметки об отправке
хранятся в базе, поэтому после перезапуска бот не теряет напоминания
и не отправляет их повторно.
"""
import logging
from datetime import datetime, timedelta

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from bot import texts
from bot.config import DAILY_DIGEST_HOUR, Config
from bot.database import Appointment, Database
from bot.keyboards import client as kb
from bot.services.notify import notify_admins
from bot.services.schedule import day_report

logger = logging.getLogger(__name__)

CHECK_INTERVAL_SECONDS = 60
LATE_REMINDER = timedelta(hours=4)


async def _send(bot: Bot, config: Config, appointment: Appointment, hours: int) -> bool:
    """Возвращает True, если напоминание можно считать обработанным."""
    try:
        today = datetime.now(config.timezone).date()
        await bot.send_message(
            appointment.user_id, texts.reminder(appointment, today), reply_markup=kb.reminder()
        )
        logger.info("Напоминание за %s ч по записи #%s отправлено", hours, appointment.id)
        return True
    except (TelegramForbiddenError, TelegramBadRequest) as e:
        # Клиент заблокировал бота или чат недоступен — повторять бессмысленно
        logger.warning("Напоминание по записи #%s не доставлено: %s", appointment.id, e)
        return True
    except Exception:
        # Сетевые и прочие временные ошибки — попробуем на следующей проверке
        logger.exception("Ошибка отправки напоминания по записи #%s", appointment.id)
        return False


async def send_reminders(bot: Bot, db: Database, config: Config) -> None:
    try:
        now = datetime.now(config.timezone)
        pending = await db.get_pending_reminders(now.date(), (now + timedelta(days=2)).date())
        for appointment in pending:
            left = appointment.starts_at(config.timezone) - now
            if left <= timedelta(0):
                await db.mark_reminded(appointment.id, day_before=True, hours_before=True)
            elif left <= timedelta(hours=2):
                if not appointment.reminded_2 and await _send(bot, config, appointment, 2):
                    await db.mark_reminded(appointment.id, day_before=True, hours_before=True)
            elif left <= timedelta(hours=24):
                if not appointment.reminded_24 and await _send(bot, config, appointment, 24):
                    # Если напоминание ушло с опозданием (бот был выключен), второе уже лишнее
                    await db.mark_reminded(
                        appointment.id, day_before=True, hours_before=left <= LATE_REMINDER
                    )
    except Exception:
        logger.exception("Ошибка в задаче напоминаний")


async def send_daily_digest(bot: Bot, db: Database, config: Config) -> None:
    """Утренняя сводка записей на сегодня для администраторов."""
    try:
        report, _ = await day_report(db, datetime.now(config.timezone).date(), "Сегодня")
        await notify_admins(bot, config, texts.admin_digest(report))
    except Exception:
        logger.exception("Ошибка при отправке утренней сводки")


def setup_scheduler(bot: Bot, db: Database, config: Config) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler(timezone=config.timezone)
    scheduler.add_job(
        send_reminders,
        "interval",
        seconds=CHECK_INTERVAL_SECONDS,
        args=(bot, db, config),
        id="reminders",
        max_instances=1,
        coalesce=True,
        next_run_time=datetime.now(config.timezone),
    )
    scheduler.add_job(
        send_daily_digest,
        "cron",
        hour=DAILY_DIGEST_HOUR,
        args=(bot, db, config),
        id="daily_digest",
        misfire_grace_time=3600,
    )
    return scheduler
