"""Онлайн-оплата через Telegram Payments: проверка перед оплатой и подтверждение записи."""
import logging
from datetime import datetime, timedelta

from aiogram import Bot, F, Router
from aiogram.types import Message, PreCheckoutQuery

from bot import texts
from bot.config import PAYMENT_TIMEOUT_MIN, Config
from bot.database import Appointment, Database
from bot.handlers.booking import INVOICE_PREFIX
from bot.keyboards import client as kb
from bot.services import slots
from bot.services.notify import notify_admins

logger = logging.getLogger(__name__)

router = Router(name="payments")


async def _invoice_appointment(db: Database, payload: str) -> Appointment | None:
    if not payload.startswith(INVOICE_PREFIX):
        return None
    try:
        appointment_id = int(payload.removeprefix(INVOICE_PREFIX))
    except ValueError:
        return None
    return await db.get_appointment(appointment_id)


def _hold_is_valid(appointment: Appointment, user_id: int, config: Config) -> bool:
    """Запись ждёт оплаты этим клиентом, и бронь ещё не истекла."""
    if appointment.status != "pending" or appointment.user_id != user_id:
        return False
    try:
        created = datetime.fromisoformat(appointment.created_at)
    except ValueError:
        return False
    return datetime.now(config.timezone) < created + timedelta(minutes=PAYMENT_TIMEOUT_MIN)


@router.pre_checkout_query()
async def on_pre_checkout(query: PreCheckoutQuery, db: Database, config: Config) -> None:
    """Telegram спрашивает перед списанием денег — подтверждаем, только если бронь в силе."""
    appointment = await _invoice_appointment(db, query.invoice_payload)
    if appointment is None or not _hold_is_valid(appointment, query.from_user.id, config):
        await query.answer(ok=False, error_message=texts.PAYMENT_EXPIRED_ALERT)
        return
    await query.answer(ok=True)


@router.message(F.successful_payment)
async def on_successful_payment(message: Message, db: Database, config: Config, bot: Bot) -> None:
    payment = message.successful_payment
    appointment = await _invoice_appointment(db, payment.invoice_payload)
    if appointment is None:
        logger.error("Оплата без записи: payload=%r, charge=%s", payment.invoice_payload, payment.telegram_payment_charge_id)
        await notify_admins(
            bot,
            config,
            "⚠️ Пришла оплата, но запись не найдена. "
            f"Код платежа: <code>{payment.telegram_payment_charge_id}</code>",
        )
        return

    confirmed = await slots.confirm_online_payment(
        db, appointment, payment.telegram_payment_charge_id, datetime.now(config.timezone)
    )
    appointment = await db.get_appointment(appointment.id)
    if not confirmed:
        logger.warning("Запись #%s оплачена, но время уже занято", appointment.id)
        await message.answer(texts.PAID_BUT_TAKEN, reply_markup=kb.main_menu())
        await notify_admins(bot, config, texts.admin_paid_but_taken(appointment))
        return

    logger.info("Запись #%s оплачена онлайн", appointment.id)
    await message.answer(texts.booked(appointment), reply_markup=kb.main_menu())
    await notify_admins(bot, config, texts.admin_new_booking(appointment))
