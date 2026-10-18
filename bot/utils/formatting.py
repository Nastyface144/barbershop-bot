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


def plural(n: int, forms: tuple[str, str, str]) -> str:
    """plural(5, ("день", "дня", "дней")) -> "дней"."""
    if n % 10 == 1 and n % 100 != 11:
        return forms[0]
    if 2 <= n % 10 <= 4 and not 12 <= n % 100 <= 14:
        return forms[1]
    return forms[2]


def day_to_key(day: date) -> str:
    return day.strftime("%Y%m%d")


def key_to_day(key: str) -> date | None:
    try:
        return datetime.strptime(key, "%Y%m%d").date()
    except (TypeError, ValueError):
        return None


def client_label(name: str, username: str | None, user_id: int | None = None) -> str:
    """Имя клиента для админа. С user_id имя кликабельно и открывает чат с клиентом."""
    label = escape(name or "Без имени")
    if user_id:
        label = f'<a href="tg://user?id={user_id}">{label}</a>'
    if username:
        label += f" (@{escape(username)})"
    return label
