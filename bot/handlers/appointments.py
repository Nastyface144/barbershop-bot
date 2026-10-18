"""«Мои записи» и отмена записи клиентом."""
import logging
from datetime import datetime

from aiogram import Bot, F, Router
from aiogram.types import CallbackQuery

from bot import texts
from bot.config import Config
from bot.database import Appointment, Database
from bot.keyboards import client as kb
from bot.keyboards.callbacks import CancelCb, MenuCb
from bot.handlers.common import show_main
from bot.services.notify import notify_admins
from bot.utils.render import notify, render

logger = logging.getLogger(__name__)

router = Router(name="appointments")


async def show_my(callback: CallbackQuery, db: Database, config: Config, notice: str = "") -> None:
    items = await db.get_user_appointments(callback.from_user.id, datetime.now(config.timezone))
    await render(callback, texts.my_appointments(items, notice), kb.my_appointments(items))


async def _cancellable(
    callback: CallbackQuery, db: Database, config: Config, appointment_id: int
) -> Appointment | None:
    """Запись принадлежит клиенту, активна (или ждёт оплаты) и ещё не началась."""
    appointment = await db.get_appointment(appointment_id)
    if (
        appointment is None
        or appointment.user_id != callback.from_user.id
        or appointment.status not in ("active", "pending")
        or appointment.starts_at(config.timezone) <= datetime.now(config.timezone)
    ):
        return None
    return appointment


@router.callback_query(MenuCb.filter(F.action == "my"))
async def on_my(callback: CallbackQuery, db: Database, config: Config) -> None:
    await show_my(callback, db, config)


@router.callback_query(CancelCb.filter(F.action == "ask"))
async def on_cancel_ask(callback: CallbackQuery, callback_data: CancelCb, db: Database, config: Config) -> None:
    appointment = await _cancellable(callback, db, config, callback_data.appointment_id)
    if appointment is None:
        await notify(callback, texts.CANCEL_UNAVAILABLE, alert=True)
        return await show_my(callback, db, config)
    await render(callback, texts.cancel_confirm(appointment), kb.cancel_confirm(appointment.id))


@router.callback_query(CancelCb.filter(F.action == "yes"))
async def on_cancel_yes(
    callback: CallbackQuery, callback_data: CancelCb, db: Database, config: Config, bot: Bot
) -> None:
    appointment = await _cancellable(callback, db, config, callback_data.appointment_id)
    if appointment is None or not await db.cancel_appointment(appointment.id):
        await notify(callback, texts.CANCEL_UNAVAILABLE, alert=True)
        return await show_my(callback, db, config)

    logger.info("Запись #%s отменена пользователем %s", appointment.id, callback.from_user.id)
    await notify(callback, "Запись отменена")
    await show_main(callback, db, config, notice=texts.CANCELLED)
    if appointment.status == "active":  # о неоплаченной брони админ и не знал
        await notify_admins(bot, config, texts.admin_cancelled(appointment))
