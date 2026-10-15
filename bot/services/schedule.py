"""Сводка записей за день — для панели админа и утренней рассылки."""
from datetime import date

from bot import texts
from bot.database import FULL_DAY, SALON, Appointment, Database


async def day_report(db: Database, day: date, label: str, notice: str = "") -> tuple[str, list[Appointment]]:
    """Текст сводки за день и список активных записей."""
    appointments = await db.get_day_appointments(day)
    closures = (await db.get_closure_rows(day, day)).get(day, set())
    masters = {m.id: m.name for m in await db.get_masters()}
    masters_off = [masters[m] for m, start in sorted(closures) if start == FULL_DAY and m in masters]
    text = texts.admin_day(
        day,
        label,
        appointments,
        salon_closed=(SALON, FULL_DAY) in closures,
        masters_off=masters_off,
        total=sum(a.price for a in appointments),
        notice=notice,
    )
    return text, appointments
