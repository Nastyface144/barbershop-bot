"""Запись клиента: услуга → мастер → дата → время → подтверждение."""
import logging
from datetime import date, datetime

from aiogram import Bot, F, Router
from aiogram.types import CallbackQuery

from bot import texts
from bot.config import Config
from bot.database import Database, Master, Service
from bot.keyboards import client as kb
from bot.keyboards.calendar import month_page
from bot.keyboards.callbacks import ConfirmCb, DayCb, MasterCb, MenuCb, ServiceCb, TimeCb
from bot.services import slots
from bot.services.notify import notify_admins
from bot.utils.formatting import key_to_day
from bot.utils.render import notify, render

logger = logging.getLogger(__name__)

router = Router(name="booking")


def _now(config: Config) -> datetime:
    return datetime.now(config.timezone)


async def _load(
    db: Database, service_id: int, master_id: int | None = None
) -> tuple[Service | None, Master | None]:
    service = await db.get_service(service_id)
    master = await db.get_master(master_id) if master_id is not None else None
    return service, master


async def _expired(callback: CallbackQuery, db: Database) -> None:
    """Данные кнопки больше не актуальны — возвращаем к выбору услуги."""
    await notify(callback, texts.SESSION_EXPIRED)
    await show_services(callback, db)


# --- Экраны ---


async def show_services(callback: CallbackQuery, db: Database) -> None:
    await render(callback, texts.choose_service(), kb.services(await db.get_services()))


async def show_masters(callback: CallbackQuery, db: Database, service: Service) -> None:
    await render(callback, texts.choose_master(service), kb.masters(service.id, await db.get_masters()))


async def show_calendar(
    callback: CallbackQuery, db: Database, config: Config, service: Service, master: Master, page: int = 0
) -> None:
    availability = await slots.get_available_days(db, service, master.id, _now(config))
    await render(
        callback, texts.choose_date(service, master), kb.calendar(service.id, master.id, availability, page)
    )


async def show_times(
    callback: CallbackQuery, db: Database, config: Config, service: Service, master: Master, day: date
) -> None:
    now = _now(config)
    free = await slots.get_free_slots(db, service, master.id, day, now)
    bookable = slots.is_bookable_day(day, now)
    page = month_page(now.date(), day) if bookable else 0
    if not free:
        await notify(callback, texts.DAY_FULL if bookable else texts.DAY_UNAVAILABLE, alert=True)
        await show_calendar(callback, db, config, service, master, page)
        return
    await render(
        callback, texts.choose_time(service, master, day), kb.times(service.id, master.id, day, free, page)
    )


# --- Обработчики ---


@router.callback_query(MenuCb.filter(F.action == "book"))
async def on_book(callback: CallbackQuery, db: Database) -> None:
    await show_services(callback, db)


@router.callback_query(ServiceCb.filter())
async def on_service(callback: CallbackQuery, callback_data: ServiceCb, db: Database) -> None:
    service, _ = await _load(db, callback_data.service_id)
    if service is None:
        return await _expired(callback, db)
    await show_masters(callback, db, service)


@router.callback_query(MasterCb.filter())
async def on_master(callback: CallbackQuery, callback_data: MasterCb, db: Database, config: Config) -> None:
    service, master = await _load(db, callback_data.service_id, callback_data.master_id)
    if service is None or master is None:
        return await _expired(callback, db)
    await show_calendar(callback, db, config, service, master, callback_data.page)


@router.callback_query(DayCb.filter())
async def on_day(callback: CallbackQuery, callback_data: DayCb, db: Database, config: Config) -> None:
    service, master = await _load(db, callback_data.service_id, callback_data.master_id)
    day = key_to_day(callback_data.day)
    if service is None or master is None or day is None:
        return await _expired(callback, db)
    await show_times(callback, db, config, service, master, day)


@router.callback_query(TimeCb.filter())
async def on_time(callback: CallbackQuery, callback_data: TimeCb, db: Database, config: Config) -> None:
    service, master = await _load(db, callback_data.service_id, callback_data.master_id)
    day = key_to_day(callback_data.day)
    if service is None or master is None or day is None:
        return await _expired(callback, db)

    free = await slots.get_free_slots(db, service, master.id, day, _now(config))
    if callback_data.minutes not in free:
        await notify(callback, texts.SLOT_TAKEN, alert=True)
        return await show_times(callback, db, config, service, master, day)

    await render(
        callback,
        texts.confirm(service, master, day, callback_data.minutes),
        kb.confirm(service.id, master.id, day, callback_data.minutes),
    )


@router.callback_query(ConfirmCb.filter())
async def on_confirm(
    callback: CallbackQuery, callback_data: ConfirmCb, db: Database, config: Config, bot: Bot
) -> None:
    service, master = await _load(db, callback_data.service_id, callback_data.master_id)
    day = key_to_day(callback_data.day)
    if service is None or master is None or day is None:
        return await _expired(callback, db)

    user = callback.from_user
    appointment = await slots.book(
        db,
        user_id=user.id,
        client_name=user.full_name,
        username=user.username,
        service=service,
        master_id=master.id,
        day=day,
        start_min=callback_data.minutes,
        now=_now(config),
    )
    if appointment is None:
        await notify(callback, texts.SLOT_TAKEN, alert=True)
        return await show_times(callback, db, config, service, master, day)

    logger.info("Новая запись #%s от пользователя %s", appointment.id, user.id)
    await notify(callback, "✅ Готово!")
    await render(callback, texts.booked(appointment), kb.booked())
    await notify_admins(bot, config, texts.admin_new_booking(appointment))
