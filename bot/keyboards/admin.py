from datetime import date

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from bot.database import DayClosure
from bot.keyboards.calendar import calendar_rows
from bot.keyboards.callbacks import AdminCb
from bot.utils.formatting import day_to_key, fmt_time

SLOTS_PER_ROW = 4


def _btn(text: str, action: str, day: date | None = None, minutes: int = -1) -> InlineKeyboardButton:
    cb = AdminCb(action=action, day=day_to_key(day) if day else "", minutes=minutes)
    return InlineKeyboardButton(text=text, callback_data=cb.pack())


def panel(today: date, tomorrow: date, today_count: int, tomorrow_count: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                _btn(f"📅 Сегодня ({today_count})", "day", today),
                _btn(f"📅 Завтра ({tomorrow_count})", "day", tomorrow),
            ],
            [_btn("🔒 Закрыть день или время", "cal")],
            [_btn("🔄 Обновить", "panel")],
        ]
    )


def day_view(day: date) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [_btn("🔒 Управлять этим днём", "manage", day)],
            [_btn("◀️ Назад", "panel")],
        ]
    )


def calendar(first: date, last: date, closures: dict[date, DayClosure]) -> InlineKeyboardMarkup:
    def cell(day: date) -> InlineKeyboardButton:
        closure = closures.get(day, DayClosure())
        if closure.full:
            label = f"🔒{day.day}"
        elif closure.slots:
            label = f"{day.day}•"
        else:
            label = str(day.day)
        return _btn(label, "manage", day)

    rows = calendar_rows(first, last, cell)
    rows.append([_btn("◀️ Назад", "panel")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def manage_day(
    day: date,
    closure: DayClosure,
    slots: list[int],
    booked_slots: set[int],
) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    if not closure.full:
        buttons = []
        for m in slots:
            if m in closure.slots:
                label = f"🔒 {fmt_time(m)}"
            elif m in booked_slots:
                label = f"👤 {fmt_time(m)}"
            else:
                label = fmt_time(m)
            buttons.append(_btn(label, "toggle_slot", day, m))
        rows.extend(buttons[i : i + SLOTS_PER_ROW] for i in range(0, len(buttons), SLOTS_PER_ROW))
        rows.append([_btn("🔒 Закрыть весь день", "toggle_day", day)])
    else:
        rows.append([_btn("🔓 Открыть день", "toggle_day", day)])
    rows.append([_btn("📋 Записи на этот день", "day", day)])
    rows.append([_btn("◀️ К календарю", "cal")])
    return InlineKeyboardMarkup(inline_keyboard=rows)
