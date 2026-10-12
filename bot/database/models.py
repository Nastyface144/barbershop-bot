from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo


@dataclass(frozen=True)
class Service:
    id: int
    emoji: str
    name: str
    price: int
    duration: int


@dataclass(frozen=True)
class Master:
    id: int
    name: str
    description: str


@dataclass(frozen=True)
class Appointment:
    id: int
    user_id: int
    client_name: str
    username: str | None
    service_id: int
    service_name: str
    master_id: int
    master_name: str
    day: date
    start_min: int
    end_min: int
    price: int
    status: str
    reminded_24: bool
    reminded_2: bool

    def starts_at(self, tz: ZoneInfo) -> datetime:
        return datetime.combine(self.day, time(), tzinfo=tz) + timedelta(minutes=self.start_min)


@dataclass(frozen=True)
class DayClosure:
    """Закрытия на конкретный день: весь день и/или отдельные слоты."""

    full: bool = False
    slots: frozenset[int] = frozenset()
