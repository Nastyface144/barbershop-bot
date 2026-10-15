"""Панель администратора: записи по дням, отмена записей, закрытие дня или времени."""
import logging
from datetime import date, datetime, timedelta

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramAPIError
from aiogram.filters import BaseFilter, Command
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message, TelegramObject

from bot import texts
from bot.config import SLOT_STEP_MIN, Config
from bot.database import FULL_DAY, SALON, Appointment, Database
from bot.keyboards import admin as kb
from bot.keyboards import client as client_kb
from bot.keyboards.callbacks import AdminApptCb, AdminCb
from bot.services import slots
from bot.utils.formatting import key_to_day
from bot.utils.render import notify, render

logger = logging.getLogger(__name__)


class IsAdmin(BaseFilter):
    async def __call__(self, event: TelegramObject, config: Config) -> bool:
        user = getattr(event, "from_user", None)
        return user is not None and user.id in config.admin_ids


router = Router(name="admin")
router.message.filter(IsAdmin())
router.callback_query.filter(IsAdmin())


def _now(config: Config) -> datetime:
    return datetime.now(config.timezone)


def _day_label(day: date, today: date) -> str:
    if day == today:
        return "Сегодня"
    if day == today + timedelta(days=1):
        return "Завтра"
    return ""


def _is_upcoming(appointment: Appointment, config: Config) -> bool:
    return appointment.status == "active" and appointment.starts_at(config.timezone) > _now(config)


async def _panel(db: Database, config: Config) -> tuple[str, InlineKeyboardMarkup]:
    today = _now(config).date()
    tomorrow = today + timedelta(days=1)
    today_count = await db.count_day_appointments(today)
    tomorrow_count = await db.count_day_appointments(tomorrow)
    return (
        texts.admin_panel(today_count, tomorrow_count),
        kb.panel(today, tomorrow, today_count, tomorrow_count),
    )


async def show_day(callback: CallbackQuery, db: Database, config: Config, day: date, notice: str = "") -> None:
    appointments = await db.get_day_appointments(day)
    closures = (await db.get_closure_rows(day, day)).get(day, set())
    masters = {m.id: m.name for m in await db.get_masters()}
    masters_off = [masters[m] for m, start in sorted(closures) if start == FULL_DAY and m in masters]
    text = texts.admin_day(
        day,
        _day_label(day, _now(config).date()),
        appointments,
        salon_closed=(SALON, FULL_DAY) in closures,
        masters_off=masters_off,
        total=sum(a.price for a in appointments),
        notice=notice,
    )
    cancellable = [a for a in appointments if _is_upcoming(a, config)]
    await render(callback, text, kb.day_view(day, cancellable))


async def show_calendar(callback: CallbackQuery, db: Database, config: Config, action: str) -> None:
    first, last = slots.booking_window(_now(config))
    closures = await db.get_closure_rows(first, last)
    await render(callback, texts.admin_calendar(action), kb.calendar(first, last, closures, action))


async def show_manage_day(callback: CallbackQuery, db: Database, day: date, master_id: int) -> None:
    masters = await db.get_masters()
    names = {m.id: m.name for m in masters}
    if master_id not in names:
        master_id = SALON

    salon = await db.get_closure(day, (SALON,))
    own = salon if master_id == SALON else await db.get_closure(day, (master_id,))
    appointments = [
        a for a in await db.get_day_appointments(day) if master_id == SALON or a.master_id == master_id
    ]
    booked = {
        slot
        for slot in slots.all_slots()
        for a in appointments
        if slot < a.end_min and a.start_min < slot + SLOT_STEP_MIN
    }
    scope = texts.SALON_SCOPE if master_id == SALON else names[master_id]
    await render(
        callback,
        texts.admin_manage_day(day, scope, own.full, salon.full, len(appointments)),
        kb.manage_day(day, master_id, masters, own, salon, slots.all_slots(), booked),
    )


def _editable_day(callback_data: AdminCb, config: Config) -> date | None:
    day = key_to_day(callback_data.day)
    if day is None or day < _now(config).date():
        return None
    return day


# --- Панель и записи ---


@router.message(Command("admin"))
async def cmd_admin(message: Message, db: Database, config: Config) -> None:
    text, markup = await _panel(db, config)
    await message.answer(text, reply_markup=markup)


@router.callback_query(AdminCb.filter(F.action == "panel"))
async def on_panel(callback: CallbackQuery, db: Database, config: Config) -> None:
    text, markup = await _panel(db, config)
    await render(callback, text, markup)


@router.callback_query(AdminCb.filter(F.action == "day"))
async def on_day(callback: CallbackQuery, callback_data: AdminCb, db: Database, config: Config) -> None:
    day = key_to_day(callback_data.day)
    if day is None:
        return await on_panel(callback, db, config)
    await show_day(callback, db, config, day)


@router.callback_query(AdminCb.filter(F.action == "pick"))
async def on_pick(callback: CallbackQuery, db: Database, config: Config) -> None:
    await show_calendar(callback, db, config, "day")


@router.callback_query(AdminApptCb.filter(F.action == "ask"))
async def on_cancel_ask(callback: CallbackQuery, callback_data: AdminApptCb, db: Database, config: Config) -> None:
    appointment = await db.get_appointment(callback_data.appointment_id)
    if appointment is None or not _is_upcoming(appointment, config):
        await notify(callback, texts.CANCEL_UNAVAILABLE, alert=True)
        if appointment is not None:
            await show_day(callback, db, config, appointment.day)
        return
    await render(callback, texts.admin_cancel_confirm(appointment), kb.cancel_confirm(appointment))


@router.callback_query(AdminApptCb.filter(F.action == "yes"))
async def on_cancel_yes(
    callback: CallbackQuery, callback_data: AdminApptCb, db: Database, config: Config, bot: Bot
) -> None:
    appointment = await db.get_appointment(callback_data.appointment_id)
    if appointment is None:
        await notify(callback, texts.CANCEL_UNAVAILABLE, alert=True)
        return await on_panel(callback, db, config)
    if not _is_upcoming(appointment, config) or not await db.cancel_appointment(appointment.id):
        await notify(callback, texts.CANCEL_UNAVAILABLE, alert=True)
        return await show_day(callback, db, config, appointment.day)

    logger.info("Админ %s отменил запись #%s", callback.from_user.id, appointment.id)
    try:
        await bot.send_message(
            appointment.user_id, texts.cancelled_by_salon(appointment), reply_markup=client_kb.rebook()
        )
        delivered = True
    except TelegramAPIError as e:
        logger.warning("Не удалось уведомить клиента об отмене записи #%s: %s", appointment.id, e)
        delivered = False

    await notify(callback, "Запись отменена")
    await show_day(callback, db, config, appointment.day, notice=texts.admin_cancelled_notice(delivered))


# --- Закрытие дней и времени ---


@router.callback_query(AdminCb.filter(F.action == "cal"))
async def on_calendar(callback: CallbackQuery, db: Database, config: Config) -> None:
    await show_calendar(callback, db, config, "manage")


@router.callback_query(AdminCb.filter(F.action == "manage"))
async def on_manage(callback: CallbackQuery, callback_data: AdminCb, db: Database, config: Config) -> None:
    day = _editable_day(callback_data, config)
    if day is None:
        await notify(callback, "Прошедшие дни изменить нельзя.", alert=True)
        return await on_calendar(callback, db, config)
    await show_manage_day(callback, db, day, callback_data.master_id)


@router.callback_query(AdminCb.filter(F.action == "toggle_day"))
async def on_toggle_day(callback: CallbackQuery, callback_data: AdminCb, db: Database, config: Config) -> None:
    day = _editable_day(callback_data, config)
    if day is None:
        await notify(callback, "Эту дату изменить нельзя.", alert=True)
        return await on_calendar(callback, db, config)
    master_id = callback_data.master_id
    if master_id != SALON and await db.get_master(master_id) is None:
        return await show_manage_day(callback, db, day, SALON)

    closed = await db.toggle_day_closed(day, master_id)
    logger.info(
        "Админ %s %s день %s (мастер %s)", callback.from_user.id, "закрыл" if closed else "открыл", day, master_id
    )
    await notify(callback, "🔒 День закрыт" if closed else "🔓 День открыт")
    await show_manage_day(callback, db, day, master_id)


@router.callback_query(AdminCb.filter(F.action == "toggle_slot"))
async def on_toggle_slot(callback: CallbackQuery, callback_data: AdminCb, db: Database, config: Config) -> None:
    day = _editable_day(callback_data, config)
    if day is None or callback_data.minutes not in slots.all_slots():
        await notify(callback, "Это время изменить нельзя.", alert=True)
        return await on_calendar(callback, db, config)
    master_id = callback_data.master_id
    if master_id != SALON:
        if await db.get_master(master_id) is None:
            return await show_manage_day(callback, db, day, SALON)
        salon = await db.get_closure(day, (SALON,))
        if salon.full or callback_data.minutes in salon.slots:
            await notify(callback, texts.SLOT_CLOSED_FOR_SALON, alert=True)
            return await show_manage_day(callback, db, day, master_id)

    closed = await db.toggle_slot_closed(day, callback_data.minutes, master_id)
    await notify(callback, "🔒 Время закрыто" if closed else "🔓 Время открыто")
    await show_manage_day(callback, db, day, master_id)
