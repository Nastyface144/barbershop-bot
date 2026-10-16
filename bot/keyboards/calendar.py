from collections.abc import Callable
from datetime import date, timedelta

from aiogram.types import DisabledButton, InlineKeyboardButton

from bot.keyboards.callbacks import NoopCb
from bot.utils.formatting import MONTHS_NOM, WEEKDAYS_HEADER


def noop_button(text: str, reason: str = "") -> InlineKeyboardButton:
    """Кнопка без действия: при нажатии бот показывает подсказку `reason`."""
    return InlineKeyboardButton(text=text, callback_data=NoopCb(reason=reason).pack())


def disabled_button(text: str) -> InlineKeyboardButton:
    """Неактивная кнопка: Telegram показывает её приглушённой, нажать на неё нельзя."""
    return InlineKeyboardButton(text=text, disabled=DisabledButton())


def _add_months(day: date, months: int) -> date:
    """Первое число месяца, отстоящего от месяца `day` на `months`."""
    index = day.year * 12 + day.month - 1 + months
    return date(index // 12, index % 12 + 1, 1)


def month_page(first: date, day: date) -> int:
    """Номер страницы календаря (месяца), на которой находится `day`."""
    return (day.year - first.year) * 12 + day.month - first.month


def calendar_rows(
    first: date,
    last: date,
    page: int,
    cell: Callable[[date], InlineKeyboardButton],
    nav: Callable[[int], str],
) -> list[list[InlineKeyboardButton]]:
    """Календарь одного месяца из окна дат `first`–`last`, со стрелками между месяцами.

    `page` — смещение месяца от месяца `first`, `nav(page)` возвращает callback_data
    для перехода на другую страницу. Прошедшие дни и дни за пределами окна записи
    показываются неактивными.
    """
    last_page = month_page(first, last)
    page = min(max(page, 0), last_page)
    month_start = _add_months(first, page)
    month_end = _add_months(first, page + 1) - timedelta(days=1)

    def arrow(text: str, target: int) -> InlineKeyboardButton:
        if 0 <= target <= last_page:
            return InlineKeyboardButton(text=text, callback_data=nav(target))
        return disabled_button(" ")

    rows = [
        [
            arrow("◀️", page - 1),
            disabled_button(f"{MONTHS_NOM[month_start.month - 1]} {month_start.year}"),
            arrow("▶️", page + 1),
        ],
        [disabled_button(name) for name in WEEKDAYS_HEADER],
    ]

    visible_first = max(first, month_start)
    visible_last = min(last, month_end)
    current = visible_first - timedelta(days=visible_first.weekday())
    end = visible_last + timedelta(days=6 - visible_last.weekday())
    week: list[InlineKeyboardButton] = []
    while current <= end:
        if current.month != month_start.month:
            week.append(disabled_button(" "))
        elif current < first or current > last:
            week.append(disabled_button(str(current.day)))
        else:
            week.append(cell(current))
        if len(week) == 7:
            rows.append(week)
            week = []
        current += timedelta(days=1)
    return rows
