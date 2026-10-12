"""Панель администратора: записи на сегодня/завтра, закрытие дня или времени."""
import logging
from datetime import date, datetime, timedelta

from aiogram import F, Router
from aiogram.filters import BaseFilter, Command
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message, TelegramObject

from bot import texts
from bot.config import SLOT_STEP_MIN, Config
from bot.database import Database
from bot.keyboards import admin as kb
from bot.keyboards.callbacks import AdminCb
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


def _today(config: Config) -> date:
    return datetime.now(config.timezone).date()


def _day_label(day: date, today: date) -> str:
    if day == today:
        return "Сегодня"
    if day == today + timedelta(days=1):
        return "Завтра"
    return ""


async def _panel(db: Database, config: Config) -> tuple[str, InlineKeyboardMarkup]:
    today = _today(config)
    tomorrow = today + timedelta(days=1)
    today_count = await db.count_day_appointments(today)
    tomorrow_count = await db.count_day_appointments(tomorrow)
    return (
        texts.admin_panel(today_count, tomorrow_count),
        kb.panel(today, tomorrow, today_count, tomorrow_count),
    )


async def show_manage_day(callback: CallbackQuery, db: Database, day: date) -> None:
    closure = await db.get_closure(day)
    appointments = await db.get_day_appointments(day)
    booked = {
        slot
        for slot in slots.all_slots()
        for a in appointments
        if slot < a.end_min and a.start_min < slot + SLOT_STEP_MIN
    }
    await render(
        callback,
        texts.admin_manage_day(day, closure.full, len(appointments)),
        kb.manage_day(day, closure, slots.all_slots(), booked),
    )


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
    appointments = await db.get_day_appointments(day)
    closure = await db.get_closure(day)
    label = _day_label(day, _today(config))
    await render(callback, texts.admin_day(day, label, appointments, closure.full), kb.day_view(day))


@router.callback_query(AdminCb.filter(F.action == "cal"))
async def on_calendar(callback: CallbackQuery, db: Database, config: Config) -> None:
    first, last = slots.booking_window(datetime.now(config.timezone))
    closures = await db.get_closures(first, last)
    await render(callback, texts.admin_calendar(), kb.calendar(first, last, closures))


@router.callback_query(AdminCb.filter(F.action == "manage"))
async def on_manage(callback: CallbackQuery, callback_data: AdminCb, db: Database, config: Config) -> None:
    day = key_to_day(callback_data.day)
    if day is None:
        return await on_calendar(callback, db, config)
    await show_manage_day(callback, db, day)


@router.callback_query(AdminCb.filter(F.action == "toggle_day"))
async def on_toggle_day(callback: CallbackQuery, callback_data: AdminCb, db: Database, config: Config) -> None:
    day = key_to_day(callback_data.day)
    if day is None or day < _today(config):
        await notify(callback, "Эту дату изменить нельзя.", alert=True)
        return await on_calendar(callback, db, config)
    closed = await db.toggle_day_closed(day)
    logger.info("Админ %s %s день %s", callback.from_user.id, "закрыл" if closed else "открыл", day)
    await notify(callback, "🔒 День закрыт" if closed else "🔓 День открыт")
    await show_manage_day(callback, db, day)


@router.callback_query(AdminCb.filter(F.action == "toggle_slot"))
async def on_toggle_slot(callback: CallbackQuery, callback_data: AdminCb, db: Database, config: Config) -> None:
    day = key_to_day(callback_data.day)
    if day is None or day < _today(config) or callback_data.minutes not in slots.all_slots():
        await notify(callback, "Это время изменить нельзя.", alert=True)
        return await on_calendar(callback, db, config)
    closed = await db.toggle_slot_closed(day, callback_data.minutes)
    await notify(callback, "🔒 Время закрыто" if closed else "🔓 Время открыто")
    await show_manage_day(callback, db, day)
