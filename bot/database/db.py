import logging
from collections import defaultdict
from datetime import date, datetime

import aiosqlite

from bot import demo_data
from bot.database.models import Appointment, DayClosure, Master, Service

logger = logging.getLogger(__name__)

FULL_DAY = -1  # значение start_min для закрытия всего дня

SCHEMA = """
CREATE TABLE IF NOT EXISTS masters (
    id          INTEGER PRIMARY KEY,
    name        TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS services (
    id       INTEGER PRIMARY KEY,
    emoji    TEXT NOT NULL DEFAULT '✂️',
    name     TEXT NOT NULL,
    price    INTEGER NOT NULL,
    duration INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS appointments (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER NOT NULL,
    client_name TEXT NOT NULL,
    username    TEXT,
    service_id  INTEGER NOT NULL REFERENCES services (id),
    master_id   INTEGER NOT NULL REFERENCES masters (id),
    day         TEXT NOT NULL,
    start_min   INTEGER NOT NULL,
    end_min     INTEGER NOT NULL,
    price       INTEGER NOT NULL,
    status      TEXT NOT NULL DEFAULT 'active',
    reminded_24 INTEGER NOT NULL DEFAULT 0,
    reminded_2  INTEGER NOT NULL DEFAULT 0,
    created_at  TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_appointments_master_day
    ON appointments (master_id, day, status);
CREATE INDEX IF NOT EXISTS idx_appointments_user
    ON appointments (user_id, status);

CREATE TABLE IF NOT EXISTS closures (
    day       TEXT NOT NULL,
    start_min INTEGER NOT NULL,
    PRIMARY KEY (day, start_min)
);
"""

APPOINTMENT_SELECT = """
SELECT a.id, a.user_id, a.client_name, a.username, a.service_id, s.name AS service_name,
       a.master_id, m.name AS master_name, a.day, a.start_min, a.end_min, a.price,
       a.status, a.reminded_24, a.reminded_2
FROM appointments a
JOIN services s ON s.id = a.service_id
JOIN masters m ON m.id = a.master_id
"""


def _appointment(row: aiosqlite.Row) -> Appointment:
    return Appointment(
        id=row["id"],
        user_id=row["user_id"],
        client_name=row["client_name"],
        username=row["username"],
        service_id=row["service_id"],
        service_name=row["service_name"],
        master_id=row["master_id"],
        master_name=row["master_name"],
        day=date.fromisoformat(row["day"]),
        start_min=row["start_min"],
        end_min=row["end_min"],
        price=row["price"],
        status=row["status"],
        reminded_24=bool(row["reminded_24"]),
        reminded_2=bool(row["reminded_2"]),
    )


class Database:
    def __init__(self, path: str) -> None:
        self.path = path
        self._conn: aiosqlite.Connection | None = None

    @property
    def conn(self) -> aiosqlite.Connection:
        if self._conn is None:
            raise RuntimeError("База данных не подключена")
        return self._conn

    async def connect(self) -> None:
        self._conn = await aiosqlite.connect(self.path)
        self._conn.row_factory = aiosqlite.Row
        await self._conn.execute("PRAGMA journal_mode=WAL")
        await self._conn.execute("PRAGMA foreign_keys=ON")
        await self._conn.executescript(SCHEMA)
        await self._seed()
        await self._conn.commit()
        logger.info("База данных готова: %s", self.path)

    async def close(self) -> None:
        if self._conn is not None:
            await self._conn.close()
            self._conn = None

    async def _seed(self) -> None:
        async with self.conn.execute("SELECT COUNT(*) FROM masters") as cur:
            (masters_count,) = await cur.fetchone()
        if not masters_count:
            await self.conn.executemany(
                "INSERT INTO masters (id, name, description) VALUES (?, ?, ?)", demo_data.MASTERS
            )
        async with self.conn.execute("SELECT COUNT(*) FROM services") as cur:
            (services_count,) = await cur.fetchone()
        if not services_count:
            await self.conn.executemany(
                "INSERT INTO services (id, emoji, name, price, duration) VALUES (?, ?, ?, ?, ?)",
                demo_data.SERVICES,
            )

    # --- Справочники ---

    async def get_services(self) -> list[Service]:
        async with self.conn.execute(
            "SELECT id, emoji, name, price, duration FROM services ORDER BY id"
        ) as cur:
            return [Service(**dict(row)) for row in await cur.fetchall()]

    async def get_service(self, service_id: int) -> Service | None:
        async with self.conn.execute(
            "SELECT id, emoji, name, price, duration FROM services WHERE id = ?", (service_id,)
        ) as cur:
            row = await cur.fetchone()
        return Service(**dict(row)) if row else None

    async def get_masters(self) -> list[Master]:
        async with self.conn.execute("SELECT id, name, description FROM masters ORDER BY id") as cur:
            return [Master(**dict(row)) for row in await cur.fetchall()]

    async def get_master(self, master_id: int) -> Master | None:
        async with self.conn.execute(
            "SELECT id, name, description FROM masters WHERE id = ?", (master_id,)
        ) as cur:
            row = await cur.fetchone()
        return Master(**dict(row)) if row else None

    # --- Занятость ---

    async def get_busy(self, master_id: int, first: date, last: date) -> dict[date, list[tuple[int, int]]]:
        """Занятые интервалы мастера по дням: {день: [(начало, конец), ...]}."""
        busy: dict[date, list[tuple[int, int]]] = defaultdict(list)
        async with self.conn.execute(
            "SELECT day, start_min, end_min FROM appointments "
            "WHERE master_id = ? AND status = 'active' AND day BETWEEN ? AND ?",
            (master_id, first.isoformat(), last.isoformat()),
        ) as cur:
            for row in await cur.fetchall():
                busy[date.fromisoformat(row["day"])].append((row["start_min"], row["end_min"]))
        return busy

    async def get_closures(self, first: date, last: date) -> dict[date, DayClosure]:
        full: set[date] = set()
        slots: dict[date, set[int]] = defaultdict(set)
        async with self.conn.execute(
            "SELECT day, start_min FROM closures WHERE day BETWEEN ? AND ?",
            (first.isoformat(), last.isoformat()),
        ) as cur:
            for row in await cur.fetchall():
                day = date.fromisoformat(row["day"])
                if row["start_min"] == FULL_DAY:
                    full.add(day)
                else:
                    slots[day].add(row["start_min"])
        return {
            day: DayClosure(full=day in full, slots=frozenset(slots.get(day, ())))
            for day in full | slots.keys()
        }

    async def get_closure(self, day: date) -> DayClosure:
        return (await self.get_closures(day, day)).get(day, DayClosure())

    async def toggle_day_closed(self, day: date) -> bool:
        """Закрывает/открывает весь день. Возвращает True, если день теперь закрыт."""
        return await self._toggle_closure(day, FULL_DAY)

    async def toggle_slot_closed(self, day: date, start_min: int) -> bool:
        return await self._toggle_closure(day, start_min)

    async def _toggle_closure(self, day: date, start_min: int) -> bool:
        cur = await self.conn.execute(
            "DELETE FROM closures WHERE day = ? AND start_min = ?", (day.isoformat(), start_min)
        )
        if cur.rowcount:
            await self.conn.commit()
            return False
        await self.conn.execute(
            "INSERT INTO closures (day, start_min) VALUES (?, ?)", (day.isoformat(), start_min)
        )
        await self.conn.commit()
        return True

    # --- Записи ---

    async def create_appointment(
        self,
        *,
        user_id: int,
        client_name: str,
        username: str | None,
        service: Service,
        master_id: int,
        day: date,
        start_min: int,
        reminded_24: bool,
        reminded_2: bool,
        created_at: datetime,
    ) -> Appointment:
        cur = await self.conn.execute(
            "INSERT INTO appointments (user_id, client_name, username, service_id, master_id, day, "
            "start_min, end_min, price, reminded_24, reminded_2, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                user_id,
                client_name,
                username,
                service.id,
                master_id,
                day.isoformat(),
                start_min,
                start_min + service.duration,
                service.price,
                int(reminded_24),
                int(reminded_2),
                created_at.isoformat(timespec="seconds"),
            ),
        )
        await self.conn.commit()
        appointment = await self.get_appointment(cur.lastrowid)
        assert appointment is not None
        return appointment

    async def get_appointment(self, appointment_id: int) -> Appointment | None:
        async with self.conn.execute(APPOINTMENT_SELECT + "WHERE a.id = ?", (appointment_id,)) as cur:
            row = await cur.fetchone()
        return _appointment(row) if row else None

    async def get_user_appointments(self, user_id: int, now: datetime) -> list[Appointment]:
        """Будущие активные записи клиента."""
        now_min = now.hour * 60 + now.minute
        today = now.date().isoformat()
        async with self.conn.execute(
            APPOINTMENT_SELECT
            + "WHERE a.user_id = ? AND a.status = 'active' "
            "AND (a.day > ? OR (a.day = ? AND a.start_min > ?)) "
            "ORDER BY a.day, a.start_min",
            (user_id, today, today, now_min),
        ) as cur:
            return [_appointment(row) for row in await cur.fetchall()]

    async def get_day_appointments(self, day: date) -> list[Appointment]:
        async with self.conn.execute(
            APPOINTMENT_SELECT + "WHERE a.day = ? AND a.status = 'active' ORDER BY a.start_min, m.id",
            (day.isoformat(),),
        ) as cur:
            return [_appointment(row) for row in await cur.fetchall()]

    async def count_day_appointments(self, day: date) -> int:
        async with self.conn.execute(
            "SELECT COUNT(*) FROM appointments WHERE day = ? AND status = 'active'", (day.isoformat(),)
        ) as cur:
            (count,) = await cur.fetchone()
        return count

    async def cancel_appointment(self, appointment_id: int) -> bool:
        cur = await self.conn.execute(
            "UPDATE appointments SET status = 'cancelled' WHERE id = ? AND status = 'active'",
            (appointment_id,),
        )
        await self.conn.commit()
        return cur.rowcount > 0

    # --- Напоминания ---

    async def get_pending_reminders(self, first: date, last: date) -> list[Appointment]:
        async with self.conn.execute(
            APPOINTMENT_SELECT
            + "WHERE a.status = 'active' AND a.day BETWEEN ? AND ? "
            "AND (a.reminded_24 = 0 OR a.reminded_2 = 0)",
            (first.isoformat(), last.isoformat()),
        ) as cur:
            return [_appointment(row) for row in await cur.fetchall()]

    async def mark_reminded(self, appointment_id: int, *, day_before: bool = False, hours_before: bool = False) -> None:
        fields = []
        if day_before:
            fields.append("reminded_24 = 1")
        if hours_before:
            fields.append("reminded_2 = 1")
        if not fields:
            return
        await self.conn.execute(
            f"UPDATE appointments SET {', '.join(fields)} WHERE id = ?", (appointment_id,)
        )
        await self.conn.commit()
