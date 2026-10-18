"""Расчёт свободного времени и безопасное создание записи."""
import asyncio
from datetime import date, datetime, timedelta

from bot.config import BOOKING_DAYS, MAX_ACTIVE_BOOKINGS, MIN_LEAD_MIN, SLOT_STEP_MIN, WORK_END_MIN, WORK_START_MIN
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


def slot_grid_for_day(
    *,
    day: date,
    duration: int,
    busy: list[tuple[int, int]],
    closure: DayClosure,
    now: datetime,
) -> list[tuple[int, bool]]:
    """Время начала на день: [(минуты, свободно ли)].

    Нерабочее время (прошедшее, закрытое админом или не помещающееся до конца дня)
    в список не попадает, занятое записями — попадает с пометкой False.
    """
    if closure.full or day < now.date():
        return []

    earliest = WORK_START_MIN
    if day == now.date():
        earliest = max(earliest, now.hour * 60 + now.minute + MIN_LEAD_MIN)

    closed = [(slot, slot + SLOT_STEP_MIN) for slot in closure.slots]
    grid = []
    for start in all_slots():
        end = start + duration
        if start < earliest or end > WORK_END_MIN or _overlaps(start, end, closed):
            continue
        grid.append((start, not _overlaps(start, end, busy)))
    return grid


def free_slots_for_day(
    *,
    day: date,
    duration: int,
    busy: list[tuple[int, int]],
    closure: DayClosure,
    now: datetime,
) -> list[int]:
    """Свободные стартовые времена для услуги длительностью `duration` минут."""
    grid = slot_grid_for_day(day=day, duration=duration, busy=busy, closure=closure, now=now)
    return [start for start, free in grid if free]


ANY_MASTER = 0  # master_id «любой мастер»: бот подберёт свободного сам


async def _master_ids(db: Database, master_id: int) -> list[int]:
    if master_id == ANY_MASTER:
        return [m.id for m in await db.get_masters()]
    return [master_id]


def _merge_grids(grids: list[list[tuple[int, bool]]]) -> list[tuple[int, bool]]:
    """Сетка «любого мастера»: время свободно, если свободно хотя бы у одного."""
    merged: dict[int, bool] = {}
    for grid in grids:
        for start, free in grid:
            merged[start] = merged.get(start, False) or free
    return sorted(merged.items())


async def get_slot_grid(
    db: Database, service: Service, master_id: int, day: date, now: datetime
) -> list[tuple[int, bool]]:
    if master_id == ANY_MASTER:
        ids = await _master_ids(db, master_id)
        return _merge_grids([await get_slot_grid(db, service, mid, day, now) for mid in ids])
    if not is_bookable_day(day, now):
        return []
    busy = await db.get_busy(master_id, day, day)
    closure = await db.get_closure(day, (SALON, master_id))
    return slot_grid_for_day(day=day, duration=service.duration, busy=busy.get(day, []), closure=closure, now=now)


async def get_free_slots(db: Database, service: Service, master_id: int, day: date, now: datetime) -> list[int]:
    return [start for start, free in await get_slot_grid(db, service, master_id, day, now) if free]


# Состояние дня в календаре клиента
DAY_FREE = "free"  # есть свободное время
DAY_FULL = "full"  # рабочий день, но всё занято
DAY_OFF = "off"  # нерабочий день или рабочее время уже прошло


async def get_available_days(db: Database, service: Service, master_id: int, now: datetime) -> dict[date, str]:
    """Состояние каждого дня окна записи: DAY_FREE, DAY_FULL или DAY_OFF."""
    if master_id == ANY_MASTER:
        per_master = [await get_available_days(db, service, mid, now) for mid in await _master_ids(db, master_id)]
        result = {}
        for day in per_master[0] if per_master else {}:
            states = {days[day] for days in per_master}
            result[day] = DAY_FREE if DAY_FREE in states else DAY_FULL if DAY_FULL in states else DAY_OFF
        return result
    first, last = booking_window(now)
    busy = await db.get_busy(master_id, first, last)
    closures = await db.get_closures(first, last, (SALON, master_id))
    result = {}
    day = first
    while day <= last:
        grid = slot_grid_for_day(
            day=day,
            duration=service.duration,
            busy=busy.get(day, []),
            closure=closures.get(day, DayClosure()),
            now=now,
        )
        if not grid:
            result[day] = DAY_OFF
        elif any(free for _, free in grid):
            result[day] = DAY_FREE
        else:
            result[day] = DAY_FULL
        day += timedelta(days=1)
    return result


class BookingError(Exception):
    """Запись не создана. reason: taken | overlap | limit."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


def overlaps_own(start: int, end: int, day: date, own: list[Appointment]) -> bool:
    """Пересекается ли время с другими записями самого клиента."""
    return any(a.day == day and start < a.end_min and a.start_min < end for a in own)


async def _pick_master(
    db: Database, service: Service, master_id: int, day: date, start_min: int, now: datetime
) -> int | None:
    """Мастер, у которого это время свободно. Для «любого» — наименее загруженный в этот день."""
    candidates = []
    for mid in await _master_ids(db, master_id):
        if start_min in await get_free_slots(db, service, mid, day, now):
            busy = await db.get_busy(mid, day, day)
            candidates.append((len(busy.get(day, [])), mid))
    return min(candidates)[1] if candidates else None


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
    payment: str = "salon",
) -> Appointment:
    """Создаёт запись. Если это невозможно, бросает BookingError с причиной.

    При онлайн-оплате запись создаётся в статусе pending: время закреплено за клиентом,
    пока он оплачивает счёт.
    """
    async with _booking_lock:
        own = await db.get_user_appointments(user_id, now, include_pending=True)
        if overlaps_own(start_min, start_min + service.duration, day, own):
            raise BookingError("overlap")
        if len(own) >= MAX_ACTIVE_BOOKINGS:
            raise BookingError("limit")
        master_id = await _pick_master(db, service, master_id, day, start_min, now)
        if master_id is None:
            raise BookingError("taken")

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
            status="pending" if payment == "online" else "active",
            payment=payment,
        )


async def confirm_online_payment(db: Database, appointment: Appointment, charge_id: str, now: datetime) -> bool:
    """Подтверждает оплаченную запись. False — время уже занято и нужен возврат денег.

    Обычно запись ещё в статусе pending. Если бронь успела истечь, пока клиент платил,
    запись восстанавливается, когда время всё ещё свободно.
    """
    async with _booking_lock:
        if appointment.status not in ("pending", "expired"):
            await db.mark_paid(appointment.id, charge_id)
            return appointment.status == "active"
        if appointment.status == "expired":
            service = await db.get_service(appointment.service_id)
            free = (
                await get_free_slots(db, service, appointment.master_id, appointment.day, now) if service else []
            )
            if appointment.start_min not in free:
                await db.mark_paid(appointment.id, charge_id)
                return False
        left = appointment.starts_at(now.tzinfo) - now
        await db.confirm_payment(
            appointment.id,
            charge_id,
            reminded_24=left <= timedelta(hours=24),
            reminded_2=left <= timedelta(hours=2),
        )
        return True
