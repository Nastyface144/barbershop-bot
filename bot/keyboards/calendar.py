from collections.abc import Callable
from datetime import date, timedelta

from aiogram.types import InlineKeyboardButton

from bot.keyboards.callbacks import NoopCb
from bot.utils.formatting import WEEKDAYS_HEADER, fmt_month_range


def noop_button(text: str, reason: str = "") -> InlineKeyboardButton:
    return InlineKeyboardButton(text=text, callback_data=NoopCb(reason=reason).pack())


def calendar_rows(
    first: date,
    last: date,
    cell: Callable[[date], InlineKeyboardButton],
) -> list[list[InlineKeyboardButton]]:
    """Сетка календаря по неделям (Пн–Вс) для дней с `first` по `last`.

    Дни вне диапазона в начале и конце недели показываются пустыми,
    прошедшие дни недели — точкой.
    """
    rows = [
        [noop_button(f"🗓 {fmt_month_range(first, last)}")],
        [noop_button(name) for name in WEEKDAYS_HEADER],
    ]
    current = first - timedelta(days=first.weekday())
    end = last + timedelta(days=6 - last.weekday())
    week: list[InlineKeyboardButton] = []
    while current <= end:
        if current < first:
            week.append(noop_button("·", "past"))
        elif current > last:
            week.append(noop_button(" "))
        else:
            week.append(cell(current))
        if len(week) == 7:
            rows.append(week)
            week = []
        current += timedelta(days=1)
    return rows
