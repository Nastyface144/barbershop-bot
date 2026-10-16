from datetime import date

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from bot import demo_data
from bot.database import Appointment, Master, Service
from bot.keyboards.calendar import calendar_rows, disabled_button, noop_button
from bot.keyboards.callbacks import (
    CancelCb,
    ConfirmCb,
    DayCb,
    MasterCb,
    MenuCb,
    ServiceCb,
    TimeCb,
)
from bot.services.slots import DAY_FREE, DAY_FULL
from bot.utils.formatting import day_to_key, fmt_date_short, fmt_price, fmt_time

TIMES_PER_ROW = 4


def _btn(text: str, cb) -> InlineKeyboardButton:
    return InlineKeyboardButton(text=text, callback_data=cb.pack())


def _back(cb) -> list[InlineKeyboardButton]:
    return [_btn("◀️ Назад", cb)]


def main_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [_btn("✂️ Записаться", MenuCb(action="book"))],
            [_btn("📋 Мои записи", MenuCb(action="my"))],
            [
                _btn("💈 Услуги и цены", MenuCb(action="services")),
                _btn("📍 Контакты", MenuCb(action="contacts")),
            ],
        ]
    )


def services_info() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [_btn("✂️ Записаться", MenuCb(action="book"))],
            _back(MenuCb(action="main")),
        ]
    )


def contacts() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🗺 Открыть на карте", url=demo_data.SHOP_MAP_URL)],
            _back(MenuCb(action="main")),
        ]
    )


def back_to_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[_back(MenuCb(action="main"))])


# --- Запись ---


def services(items: list[Service]) -> InlineKeyboardMarkup:
    rows = [
        [_btn(f"{s.emoji} {s.name} · {fmt_price(s.price)}", ServiceCb(service_id=s.id))]
        for s in items
    ]
    rows.append(_back(MenuCb(action="main")))
    return InlineKeyboardMarkup(inline_keyboard=rows)


def masters(service_id: int, items: list[Master]) -> InlineKeyboardMarkup:
    rows = [
        [_btn(f"👤 {m.name} — {m.description}", MasterCb(service_id=service_id, master_id=m.id))]
        for m in items
    ]
    rows.append(_back(MenuCb(action="book")))
    return InlineKeyboardMarkup(inline_keyboard=rows)


def calendar(service_id: int, master_id: int, availability: dict[date, str], page: int) -> InlineKeyboardMarkup:
    days = sorted(availability)

    def cell(day: date) -> InlineKeyboardButton:
        state = availability.get(day)
        if state == DAY_FREE:
            return _btn(str(day.day), DayCb(service_id=service_id, master_id=master_id, day=day_to_key(day)))
        if state == DAY_FULL:
            return noop_button("✖", "full")
        return disabled_button(str(day.day))

    def nav(target: int) -> str:
        return MasterCb(service_id=service_id, master_id=master_id, page=target).pack()

    rows = calendar_rows(days[0], days[-1], page, cell, nav)
    rows.append(_back(ServiceCb(service_id=service_id)))
    return InlineKeyboardMarkup(inline_keyboard=rows)


def times(service_id: int, master_id: int, day: date, grid: list[tuple[int, bool]], page: int) -> InlineKeyboardMarkup:
    """Сетка времени: свободное можно выбрать, занятое показано крестиком и неактивно."""
    key = day_to_key(day)
    buttons = [
        _btn(fmt_time(m), TimeCb(service_id=service_id, master_id=master_id, day=key, minutes=m))
        if free
        else disabled_button(f"✖ {fmt_time(m)}")
        for m, free in grid
    ]
    rows = [buttons[i : i + TIMES_PER_ROW] for i in range(0, len(buttons), TIMES_PER_ROW)]
    rows.append(_back(MasterCb(service_id=service_id, master_id=master_id, page=page)))
    return InlineKeyboardMarkup(inline_keyboard=rows)


def confirm(service_id: int, master_id: int, day: date, minutes: int, online: bool) -> InlineKeyboardMarkup:
    key = day_to_key(day)

    def pay(method: str) -> ConfirmCb:
        return ConfirmCb(service_id=service_id, master_id=master_id, day=key, minutes=minutes, pay=method)

    if online:
        rows = [
            [_btn("💳 Оплатить онлайн", pay("online"))],
            [_btn("💵 В салоне: наличные или карта", pay("salon"))],
        ]
    else:
        rows = [[_btn("✅ Подтвердить запись", pay("salon"))]]
    rows.append(_back(DayCb(service_id=service_id, master_id=master_id, day=key)))
    return InlineKeyboardMarkup(inline_keyboard=rows)


def awaiting_payment(appointment_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[_btn("❌ Отменить запись", CancelCb(appointment_id=appointment_id, action="ask"))]]
    )


# --- Мои записи ---


def my_appointments(items: list[Appointment]) -> InlineKeyboardMarkup:
    rows = [
        [
            _btn(
                f"❌ Отменить · {fmt_date_short(a.day)}, {fmt_time(a.start_min)}",
                CancelCb(appointment_id=a.id, action="ask"),
            )
        ]
        for a in items
    ]
    if not items:
        rows.append([_btn("✂️ Записаться", MenuCb(action="book"))])
    rows.append(_back(MenuCb(action="main")))
    return InlineKeyboardMarkup(inline_keyboard=rows)


def cancel_confirm(appointment_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [_btn("❌ Да, отменить", CancelCb(appointment_id=appointment_id, action="yes"))],
            _back(MenuCb(action="my")),
        ]
    )


def reminder() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[_btn("📋 Мои записи", MenuCb(action="my"))]])



def rebook() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [_btn("✂️ Записаться снова", MenuCb(action="book"))],
            [_btn("📋 Мои записи", MenuCb(action="my"))],
        ]
    )
