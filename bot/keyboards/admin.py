from datetime import date, timedelta

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from bot.database import FULL_DAY, SALON, Appointment, DayClosure, Master
from bot.keyboards.calendar import calendar_rows
from bot.keyboards.callbacks import AdminApptCb, AdminCb
from bot.utils.formatting import day_to_key, fmt_date_short, fmt_time

SLOTS_PER_ROW = 4
TABS_PER_ROW = 2
CLIENT_NAME_LIMIT = 14
MAX_CANCEL_BUTTONS = 40  # у Telegram есть предел на число кнопок в сообщении


def _btn(
    text: str, action: str, day: date | None = None, minutes: int = -1, master_id: int = SALON
) -> InlineKeyboardButton:
    cb = AdminCb(action=action, day=day_to_key(day) if day else "", minutes=minutes, master_id=master_id)
    return InlineKeyboardButton(text=text, callback_data=cb.pack())


def panel(today: date, tomorrow: date, today_count: int, tomorrow_count: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                _btn(f"📅 Сегодня ({today_count})", "day", today),
                _btn(f"📅 Завтра ({tomorrow_count})", "day", tomorrow),
            ],
            [_btn("🗓 Записи на другую дату", "pick")],
            [_btn("🔒 Закрыть день или время", "cal")],
            [_btn("🔄 Обновить", "panel")],
        ]
    )


def _short_name(name: str) -> str:
    return name if len(name) <= CLIENT_NAME_LIMIT else name[: CLIENT_NAME_LIMIT - 1] + "…"


def day_view(day: date, cancellable: list[Appointment]) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(
                text=f"❌ {fmt_time(a.start_min)} · {a.master_name} · {_short_name(a.client_name)}",
                callback_data=AdminApptCb(appointment_id=a.id, action="ask").pack(),
            )
        ]
        for a in cancellable[:MAX_CANCEL_BUTTONS]
    ]
    prev_day, next_day = day - timedelta(days=1), day + timedelta(days=1)
    rows.append(
        [
            _btn(f"⬅️ {fmt_date_short(prev_day)}", "day", prev_day),
            _btn(f"{fmt_date_short(next_day)} ➡️", "day", next_day),
        ]
    )
    rows.append([_btn("🔒 Закрыть время в этот день", "manage", day)])
    rows.append([_btn("◀️ В панель", "panel")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def cancel_confirm(appointment: Appointment) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="❌ Да, отменить",
                    callback_data=AdminApptCb(appointment_id=appointment.id, action="yes").pack(),
                )
            ],
            [_btn("◀️ Назад", "day", appointment.day)],
        ]
    )


def calendar(
    first: date, last: date, closures: dict[date, set[tuple[int, int]]], action: str, page: int
) -> InlineKeyboardMarkup:
    """Календарь админа. action: day — открыть записи, manage — управление закрытиями."""

    def cell(day: date) -> InlineKeyboardButton:
        rows = closures.get(day, set())
        if (SALON, FULL_DAY) in rows:
            label = f"🔒{day.day}"
        elif rows:
            label = f"{day.day}•"
        else:
            label = str(day.day)
        return _btn(label, action, day)

    def nav(target: int) -> str:
        nav_action = "pick" if action == "day" else "cal"
        return AdminCb(action=nav_action, page=target).pack()

    rows = calendar_rows(first, last, page, cell, nav)
    rows.append([_btn("◀️ В панель", "panel")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def manage_day(
    day: date,
    master_id: int,
    masters: list[Master],
    own: DayClosure,
    salon: DayClosure,
    slots: list[int],
    booked_slots: set[int],
    calendar_page: int,
) -> InlineKeyboardMarkup:
    """Сетка времени дня. own — закрытия выбранного раздела, salon — закрытия всего салона."""
    tabs = [_btn(("✅ " if master_id == SALON else "") + "🏠 Салон", "manage", day)]
    tabs += [
        _btn(("✅ " if master_id == m.id else "") + m.name, "manage", day, master_id=m.id) for m in masters
    ]
    rows: list[list[InlineKeyboardButton]] = [tabs[i : i + TABS_PER_ROW] for i in range(0, len(tabs), TABS_PER_ROW)]

    if salon.full and master_id != SALON:
        rows.append([_btn("🏠 Перейти к настройкам салона", "manage", day)])
    elif own.full:
        rows.append([_btn("🔓 Открыть день", "toggle_day", day, master_id=master_id)])
    else:
        buttons = []
        for m in slots:
            if m in own.slots:
                label = f"🔒 {fmt_time(m)}"
            elif master_id != SALON and m in salon.slots:
                label = f"🏠 {fmt_time(m)}"
            elif m in booked_slots:
                label = f"👤 {fmt_time(m)}"
            else:
                label = fmt_time(m)
            buttons.append(_btn(label, "toggle_slot", day, m, master_id))
        rows.extend(buttons[i : i + SLOTS_PER_ROW] for i in range(0, len(buttons), SLOTS_PER_ROW))
        rows.append([_btn("🔒 Закрыть весь день", "toggle_day", day, master_id=master_id)])

    rows.append([_btn("📋 Записи на этот день", "day", day)])
    back = AdminCb(action="cal", page=calendar_page).pack()
    rows.append([InlineKeyboardButton(text="◀️ К календарю", callback_data=back)])
    return InlineKeyboardMarkup(inline_keyboard=rows)
