"""Расчёт свободного времени и безопасное создание записи."""
import asyncio
from datetime import date, datetime, timedelta

from bot.config import BOOKING_DAYS, MIN_LEAD_MIN, SLOT_STEP_MIN, WORK_END_MIN, WORK_START_MIN
from bot.database import SALON, Appointment, Database, DayClosure, Service

# Защита от гонки: два клиента не смогут одновременно занять одно время
_booking_lock = asyncio.Lock()


def booking_window(now: datetime) -> tuple[date, date]:
    today = now.date()
    return today, today + timedelta(days=BOOKING_DAYS - 1)


def is_bookable_day(day: date, now: datetime) -> bool:
    first, last = booking_window(now)
    return first <= day <= last


def all_slots() -> list[int]:
    """Все стартовые точки сетки рабочего дня."""
    return list(range(WORK_START_MIN, WORK_END_MIN, SLOT_STEP_MIN))


def _overlaps(start: int, end: int, intervals: list[tuple[int, int]]) -> bool:
    return any(start < b_end and b_start < end for b_start, b_end in intervals)


def free_slots_for_day(
    *,
    day: date,
    duration: int,
    busy: list[tuple[int, int]],
    closure: DayClosure,
    now: datetime,
) -> list[int]:
    """Свободные стартовые времена для услуги длительностью `duration` минут."""
    if closure.full or day < now.date():
        return []

    earliest = WORK_START_MIN
    if day == now.date():
        earliest = max(earliest, now.hour * 60 + now.minute + MIN_LEAD_MIN)

    closed = [(slot, slot + SLOT_STEP_MIN) for slot in closure.slots]
    result = []
    for start in all_slots():
        end = start + duration
        if start < earliest or end > WORK_END_MIN:
            continue
        if _overlaps(start, end, busy) or _overlaps(start, end, closed):
            continue
        result.append(start)
    return result


async def get_free_slots(db: Database, service: Service, master_id: int, day: date, now: datetime) -> list[int]:
    if not is_bookable_day(day, now):
        return []
    busy = await db.get_busy(master_id, day, day)
    closure = await db.get_closure(day, (SALON, master_id))
    return free_slots_for_day(
        day=day, duration=service.duration, busy=busy.get(day, []), closure=closure, now=now
    )


async def get_available_days(db: Database, service: Service, master_id: int, now: datetime) -> dict[date, bool]:
    """Для каждого дня окна записи: есть ли хотя бы одно свободное время."""
    first, last = booking_window(now)
    busy = await db.get_busy(master_id, first, last)
    closures = await db.get_closures(first, last, (SALON, master_id))
    result = {}
    day = first
    while day <= last:
        slots = free_slots_for_day(
            day=day,
            duration=service.duration,
            busy=busy.get(day, []),
            closure=closures.get(day, DayClosure()),
            now=now,
        )
        result[day] = bool(slots)
        day += timedelta(days=1)
    return result


async def book(
    db: Database,
    *,
    user_id: int,
    client_name: str,
    username: str | None,
    service: Service,
    master_id: int,
    day: date,
    start_min: int,
    now: datetime,
) -> Appointment | None:
    """Создаёт запись, если время всё ещё свободно. Иначе возвращает None."""
    async with _booking_lock:
        if start_min not in await get_free_slots(db, service, master_id, day, now):
            return None

        starts_at = datetime.combine(day, datetime.min.time(), tzinfo=now.tzinfo) + timedelta(minutes=start_min)
        left = starts_at - now
        # Если до визита уже меньше суток (или 2 часов), такое напоминание не нужно
        return await db.create_appointment(
            user_id=user_id,
            client_name=client_name,
            username=username,
            service=service,
            master_id=master_id,
            day=day,
            start_min=start_min,
            reminded_24=left <= timedelta(hours=24),
            reminded_2=left <= timedelta(hours=2),
            created_at=now,
        )
