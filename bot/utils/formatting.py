from datetime import date, datetime
from html import escape

WEEKDAYS_SHORT = ["пн", "вт", "ср", "чт", "пт", "сб", "вс"]
WEEKDAYS_HEADER = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
MONTHS_GEN = [
    "января", "февраля", "марта", "апреля", "мая", "июня",
    "июля", "августа", "сентября", "октября", "ноября", "декабря",
]
MONTHS_NOM = [
    "Январь", "Февраль", "Март", "Апрель", "Май", "Июнь",
    "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь",
]


def fmt_time(minutes: int) -> str:
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def fmt_date(day: date) -> str:
    """пн, 14 октября"""
    return f"{WEEKDAYS_SHORT[day.weekday()]}, {day.day} {MONTHS_GEN[day.month - 1]}"


def fmt_date_short(day: date) -> str:
    """14.10"""
    return f"{day.day:02d}.{day.month:02d}"


def fmt_price(price: int) -> str:
    return f"{price:,}".replace(",", " ") + " ₽"


def fmt_duration(minutes: int) -> str:
    hours, mins = divmod(minutes, 60)
    if hours and mins:
        return f"{hours} ч {mins} мин"
    if hours:
        return f"{hours} ч"
    return f"{mins} мин"


def fmt_month_range(first: date, last: date) -> str:
    if (first.year, first.month) == (last.year, last.month):
        return f"{MONTHS_NOM[first.month - 1]} {first.year}"
    if first.year == last.year:
        return f"{MONTHS_NOM[first.month - 1]} – {MONTHS_NOM[last.month - 1].lower()} {last.year}"
    return f"{MONTHS_NOM[first.month - 1]} {first.year} – {MONTHS_NOM[last.month - 1].lower()} {last.year}"


def day_to_key(day: date) -> str:
    return day.strftime("%Y%m%d")


def key_to_day(key: str) -> date | None:
    try:
        return datetime.strptime(key, "%Y%m%d").date()
    except (TypeError, ValueError):
        return None


def client_label(name: str, username: str | None) -> str:
    label = escape(name or "Без имени")
    if username:
        label += f" (@{escape(username)})"
    return label
