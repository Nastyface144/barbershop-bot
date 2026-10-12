import os
from dataclasses import dataclass
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from dotenv import load_dotenv

# Рабочий график и параметры записи (в минутах от начала суток)
WORK_START_MIN = 10 * 60  # 10:00
WORK_END_MIN = 20 * 60  # 20:00
SLOT_STEP_MIN = 30  # шаг сетки времени
BOOKING_DAYS = 14  # на сколько дней вперёд открыта запись
MIN_LEAD_MIN = 30  # не раньше чем за 30 минут до начала


@dataclass(frozen=True)
class Config:
    bot_token: str
    admin_ids: frozenset[int]
    timezone: ZoneInfo
    db_path: str


class ConfigError(RuntimeError):
    pass


def load_config() -> Config:
    load_dotenv()

    token = os.getenv("BOT_TOKEN", "").strip()
    if not token:
        raise ConfigError("BOT_TOKEN не задан. Скопируйте .env.example в .env и укажите токен бота.")

    admin_ids: set[int] = set()
    for part in os.getenv("ADMIN_ID", "").split(","):
        part = part.strip()
        if not part:
            continue
        try:
            admin_ids.add(int(part))
        except ValueError:
            raise ConfigError(f"ADMIN_ID должен быть числом, получено: {part!r}") from None

    tz_name = os.getenv("TIMEZONE", "Europe/Moscow").strip() or "Europe/Moscow"
    try:
        timezone = ZoneInfo(tz_name)
    except ZoneInfoNotFoundError:
        raise ConfigError(f"Неизвестный часовой пояс: {tz_name!r}") from None

    db_path = os.getenv("DB_PATH", "barbershop.db").strip() or "barbershop.db"

    return Config(
        bot_token=token,
        admin_ids=frozenset(admin_ids),
        timezone=timezone,
        db_path=db_path,
    )
