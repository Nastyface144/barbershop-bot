import os
from dataclasses import dataclass
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from dotenv import load_dotenv

load_dotenv()


def _booking_days() -> int:
    """На сколько дней вперёд открыта запись: BOOKING_DAYS из .env, от 1 до 90, по умолчанию 30."""
    try:
        days = int(os.getenv("BOOKING_DAYS", "30"))
    except ValueError:
        days = 30
    return min(max(days, 1), 90)


# Рабочий график и параметры записи (в минутах от начала суток)
WORK_START_MIN = 10 * 60  # 10:00
WORK_END_MIN = 20 * 60  # 20:00
SLOT_STEP_MIN = 30  # шаг сетки времени
BOOKING_DAYS = _booking_days()
MIN_LEAD_MIN = 30  # не раньше чем за 30 минут до начала
MAX_ACTIVE_BOOKINGS = 3  # сколько будущих записей может быть у одного клиента
DAILY_DIGEST_HOUR = 9  # во сколько админ получает план на день
PAYMENT_TIMEOUT_MIN = 15  # сколько минут время держится за клиентом, пока он оплачивает онлайн
PAYMENT_CURRENCY = "RUB"


@dataclass(frozen=True)
class Config:
    bot_token: str
    admin_ids: frozenset[int]
    timezone: ZoneInfo
    db_path: str
    payment_token: str = ""  # токен платёжного провайдера от @BotFather; пусто — только оплата в салоне


class ConfigError(RuntimeError):
    pass


def load_config() -> Config:
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
        payment_token=os.getenv("PAYMENT_TOKEN", "").strip(),
    )
