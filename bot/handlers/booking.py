"""Запись клиента: услуга → мастер → дата → время → подтверждение."""
import logging
from datetime import date, datetime

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramAPIError
from aiogram.types import CallbackQuery, LabeledPrice

from bot import texts
from bot.config import MAX_ACTIVE_BOOKINGS, PAYMENT_CURRENCY, Config
from bot.database import Appointment, Database, Master, Service
from bot.handlers.appointments import show_my
from bot.keyboards import client as kb
from bot.keyboards.calendar import month_page
from bot.keyboards.callbacks import ConfirmCb, DayCb, MasterCb, MenuCb, ServiceCb, TimeCb
from bot.services import slots
from bot.services.notify import notify_admins
from bot.utils.formatting import key_to_day
from bot.utils.render import notify, render

logger = logging.getLogger(__name__)

router = Router(name="booking")

INVOICE_PREFIX = "appointment:"  # payload счёта: appointment:<id>

BOOKING_ERRORS = {
    "taken": texts.SLOT_TAKEN,
    "overlap": texts.BOOKING_OVERLAP,
    "limit": texts.BOOKING_LIMIT,
}


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


async def _grid_for_client(
    callback: CallbackQuery, db: Database, service: Service, master_id: int, day: date, now: datetime
) -> list[tuple[int, bool]]:
    """Сетка времени мастера; время, пересекающееся с другими записями самого клиента, — занято."""
    grid = await slots.get_slot_grid(db, service, master_id, day, now)
    own = await db.get_user_appointments(callback.from_user.id, now, include_pending=True)
    return [(m, free and not slots.overlaps_own(m, m + service.duration, day, own)) for m, free in grid]


async def show_times(
    callback: CallbackQuery, db: Database, config: Config, service: Service, master: Master, day: date
) -> None:
    now = _now(config)
    grid = await _grid_for_client(callback, db, service, master.id, day, now)
    bookable = slots.is_bookable_day(day, now)
    page = month_page(now.date(), day) if bookable else 0
    if not any(free for _, free in grid):
        await notify(callback, texts.DAY_FULL if bookable else texts.DAY_UNAVAILABLE, alert=True)
        await show_calendar(callback, db, config, service, master, page)
        return
    await render(
        callback, texts.choose_time(service, master, day), kb.times(service.id, master.id, day, grid, page)
    )


async def show_confirm(
    callback: CallbackQuery, config: Config, service: Service, master: Master, day: date, minutes: int
) -> None:
    online = bool(config.payment_token)
    await render(
        callback,
        texts.confirm(service, master, day, minutes, online),
        kb.confirm(service.id, master.id, day, minutes, online),
    )


# --- Обработчики ---


@router.callback_query(MenuCb.filter(F.action == "book"))
async def on_book(callback: CallbackQuery, db: Database, config: Config) -> None:
    own = await db.get_user_appointments(callback.from_user.id, _now(config))
    if len(own) >= MAX_ACTIVE_BOOKINGS:
        await notify(callback, texts.BOOKING_LIMIT, alert=True)
        return await show_my(callback, db, config)
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

    grid = await _grid_for_client(callback, db, service, master.id, day, _now(config))
    if (callback_data.minutes, True) not in grid:
        await notify(callback, texts.SLOT_TAKEN, alert=True)
        return await show_times(callback, db, config, service, master, day)

    await show_confirm(callback, config, service, master, day, callback_data.minutes)


@router.callback_query(ConfirmCb.filter())
async def on_confirm(
    callback: CallbackQuery, callback_data: ConfirmCb, db: Database, config: Config, bot: Bot
) -> None:
    service, master = await _load(db, callback_data.service_id, callback_data.master_id)
    day = key_to_day(callback_data.day)
    if service is None or master is None or day is None:
        return await _expired(callback, db)

    online = callback_data.pay == "online"
    if online and not config.payment_token:
        await notify(callback, texts.PAYMENT_UNAVAILABLE, alert=True)
        return await show_confirm(callback, config, service, master, day, callback_data.minutes)

    user = callback.from_user
    try:
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
            payment="online" if online else "salon",
        )
    except slots.BookingError as e:
        await notify(callback, BOOKING_ERRORS[e.reason], alert=True)
        if e.reason == "limit":
            return await show_my(callback, db, config)
        return await show_times(callback, db, config, service, master, day)

    if online:
        return await _request_payment(callback, db, config, bot, appointment, service, master)

    logger.info("Новая запись #%s от пользователя %s", appointment.id, user.id)
    await notify(callback, "✅ Готово!")
    await render(callback, texts.booked(appointment), kb.main_menu())
    await notify_admins(bot, config, texts.admin_new_booking(appointment))


async def _request_payment(
    callback: CallbackQuery,
    db: Database,
    config: Config,
    bot: Bot,
    appointment: Appointment,
    service: Service,
    master: Master,
) -> None:
    """Время закреплено за клиентом — отправляем счёт. Подтверждение придёт после оплаты."""
    try:
        await bot.send_invoice(
            chat_id=callback.from_user.id,
            title=texts.invoice_title(),
            description=texts.invoice_description(appointment),
            payload=f"{INVOICE_PREFIX}{appointment.id}",
            provider_token=config.payment_token,
            currency=PAYMENT_CURRENCY,
            prices=[LabeledPrice(label=appointment.service_name, amount=appointment.price * 100)],
        )
    except TelegramAPIError as e:
        logger.error("Не удалось выставить счёт по записи #%s: %s", appointment.id, e)
        await db.cancel_appointment(appointment.id)
        await notify(callback, texts.PAYMENT_UNAVAILABLE, alert=True)
        return await show_confirm(callback, config, service, master, appointment.day, appointment.start_min)

    logger.info("Запись #%s ждёт онлайн-оплаты", appointment.id)
    await render(callback, texts.awaiting_payment(appointment), kb.awaiting_payment(appointment.id))
