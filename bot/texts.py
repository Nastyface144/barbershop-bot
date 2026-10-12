"""Тексты экранов бота."""
from datetime import date, timedelta
from html import escape

from bot import demo_data
from bot.database import Appointment, Master, Service
from bot.utils.formatting import (
    client_label,
    fmt_date,
    fmt_duration,
    fmt_price,
    fmt_time,
)

TOTAL_STEPS = 4


def welcome(name: str) -> str:
    return (
        f"💈 <b>{escape(demo_data.SHOP_NAME)}</b>\n\n"
        f"Привет, {escape(name)}! Здесь можно записаться к барберу за минуту — "
        "без звонков и ожидания.\n\n"
        "Выберите, что нужно 👇"
    )


def services_and_prices(services: list[Service]) -> str:
    lines = ["💈 <b>Услуги и цены</b>\n"]
    for s in services:
        lines.append(f"{s.emoji} <b>{escape(s.name)}</b>\n      {fmt_price(s.price)} · {fmt_duration(s.duration)}")
    return "\n".join(lines)


def contacts() -> str:
    return (
        f"📍 <b>Контакты</b>\n\n"
        f"🏠 {escape(demo_data.SHOP_ADDRESS)}\n"
        f"📞 {escape(demo_data.SHOP_PHONE)}\n"
        f"🕐 {escape(demo_data.SHOP_HOURS)}"
    )


def _step(n: int) -> str:
    return f"✂️ <b>Запись · шаг {n} из {TOTAL_STEPS}</b>"


def _summary(service: Service | None = None, master: Master | None = None, day: date | None = None) -> str:
    lines = []
    if service:
        lines.append(f"Услуга: <b>{escape(service.name)}</b>")
    if master:
        lines.append(f"Мастер: <b>{escape(master.name)}</b>")
    if day:
        lines.append(f"Дата: <b>{fmt_date(day)}</b>")
    return "\n".join(lines)


def choose_service() -> str:
    return f"{_step(1)}\n\nВыберите услугу:"


def choose_master(service: Service) -> str:
    return f"{_step(2)}\n\n{_summary(service)}\n\nВыберите мастера:"


def choose_date(service: Service, master: Master) -> str:
    return f"{_step(3)}\n\n{_summary(service, master)}\n\nВыберите дату:"


def choose_time(service: Service, master: Master, day: date) -> str:
    return f"{_step(4)}\n\n{_summary(service, master, day)}\n\nВыберите время:"


def _details(service_name: str, master_name: str, day: date, start: int, end: int, price: int) -> str:
    return (
        f"✂️ Услуга: <b>{escape(service_name)}</b>\n"
        f"👤 Мастер: <b>{escape(master_name)}</b>\n"
        f"🗓 Дата: <b>{fmt_date(day)}</b>\n"
        f"🕐 Время: <b>{fmt_time(start)}–{fmt_time(end)}</b>\n"
        f"💰 Стоимость: <b>{fmt_price(price)}</b>"
    )


def confirm(service: Service, master: Master, day: date, start: int) -> str:
    details = _details(service.name, master.name, day, start, start + service.duration, service.price)
    return f"📝 <b>Проверьте запись</b>\n\n{details}\n\nВсё верно?"


def booked(a: Appointment) -> str:
    details = _details(a.service_name, a.master_name, a.day, a.start_min, a.end_min, a.price)
    return (
        f"✅ <b>Вы записаны!</b>\n\n{details}\n\n"
        f"📍 {escape(demo_data.SHOP_ADDRESS)}\n\n"
        "Напомним о визите за сутки и за 2 часа. Ждём вас!"
    )


SLOT_TAKEN = "😔 Это время только что заняли. Выберите другое."
DAY_FULL = "На этот день свободного времени не осталось."
DAY_UNAVAILABLE = "Эта дата недоступна для записи."
SESSION_EXPIRED = "Данные устарели, начните заново."


def my_appointments(appointments: list[Appointment], notice: str = "") -> str:
    head = f"{notice}\n\n" if notice else ""
    if not appointments:
        return f"{head}📋 <b>Мои записи</b>\n\nУ вас пока нет предстоящих записей."
    lines = [f"{head}📋 <b>Мои записи</b>"]
    for i, a in enumerate(appointments, 1):
        lines.append(
            f"\n<b>{i}. {fmt_date(a.day)}, {fmt_time(a.start_min)}</b>\n"
            f"✂️ {escape(a.service_name)} — {fmt_price(a.price)}\n"
            f"👤 Мастер: {escape(a.master_name)}"
        )
    return "\n".join(lines)


def cancel_confirm(a: Appointment) -> str:
    details = _details(a.service_name, a.master_name, a.day, a.start_min, a.end_min, a.price)
    return f"❓ <b>Отменить запись?</b>\n\n{details}"


CANCELLED = "✅ Запись отменена."
CANCEL_UNAVAILABLE = "Эту запись уже нельзя отменить."


def reminder(a: Appointment, today: date) -> str:
    if a.day == today:
        when = "Сегодня"
    elif a.day == today + timedelta(days=1):
        when = "Завтра"
    else:
        when = fmt_date(a.day).capitalize()
    return (
        f"⏰ <b>Напоминание о визите</b>\n\n"
        f"{when} в {fmt_time(a.start_min)} вас ждут в {escape(demo_data.SHOP_NAME)}.\n\n"
        f"✂️ {escape(a.service_name)}\n"
        f"👤 Мастер: {escape(a.master_name)}\n"
        f"🗓 {fmt_date(a.day)}, {fmt_time(a.start_min)}–{fmt_time(a.end_min)}\n"
        f"📍 {escape(demo_data.SHOP_ADDRESS)}\n\n"
        "Если планы изменились, отмените запись в разделе «Мои записи»."
    )


# --- Админ ---


def _admin_details(a: Appointment) -> str:
    return (
        f"👤 {client_label(a.client_name, a.username)}\n"
        f"✂️ {escape(a.service_name)} — {fmt_price(a.price)}\n"
        f"💈 Мастер: {escape(a.master_name)}\n"
        f"🗓 {fmt_date(a.day)}, {fmt_time(a.start_min)}–{fmt_time(a.end_min)}"
    )


def admin_new_booking(a: Appointment) -> str:
    return f"🆕 <b>Новая запись</b>\n\n{_admin_details(a)}"


def admin_cancelled(a: Appointment) -> str:
    return f"❌ <b>Клиент отменил запись</b>\n\n{_admin_details(a)}"


def admin_panel(today_count: int, tomorrow_count: int) -> str:
    return (
        "🛠 <b>Панель администратора</b>\n\n"
        f"📅 Сегодня: <b>{today_count}</b> {_records_word(today_count)}\n"
        f"📅 Завтра: <b>{tomorrow_count}</b> {_records_word(tomorrow_count)}"
    )


def admin_day(day: date, label: str, appointments: list[Appointment], closed: bool) -> str:
    title = f"{label}, {fmt_date(day)}" if label else fmt_date(day).capitalize()
    head = f"📅 <b>{title}</b>"
    if closed:
        head += "\n🔒 День закрыт для записи"
    if not appointments:
        return f"{head}\n\nЗаписей нет."
    blocks = [head]
    for a in appointments:
        blocks.append(
            f"<b>{fmt_time(a.start_min)}–{fmt_time(a.end_min)}</b> · {escape(a.master_name)}\n"
            f"✂️ {escape(a.service_name)} — {fmt_price(a.price)}\n"
            f"👤 {client_label(a.client_name, a.username)}"
        )
    return "\n\n".join(blocks)


def admin_calendar() -> str:
    return (
        "🔒 <b>Закрыть день или время</b>\n\n"
        "Выберите дату.\n"
        "🔒 — день закрыт, • — закрыта часть времени."
    )


def admin_manage_day(day: date, closed: bool, appointments_count: int) -> str:
    status = "🔒 закрыт" if closed else "🟢 открыт"
    text = (
        f"🗓 <b>{fmt_date(day)}</b>\n\n"
        f"Статус: {status}\n"
        f"Записей: {appointments_count}\n\n"
    )
    if closed:
        text += "Откройте день, чтобы клиенты снова могли записаться."
    else:
        text += "Нажмите на время, чтобы закрыть или открыть его.\n🔒 — закрыто, 👤 — есть запись."
    if appointments_count:
        text += "\n\n⚠️ Закрытие не отменяет уже созданные записи."
    return text


def _records_word(n: int) -> str:
    if n % 10 == 1 and n % 100 != 11:
        return "запись"
    if 2 <= n % 10 <= 4 and not 12 <= n % 100 <= 14:
        return "записи"
    return "записей"


ADMIN_ONLY = "⛔ Эта команда доступна только администратору."
UNKNOWN_MESSAGE = "Я работаю через кнопки 👇"
STALE_BUTTON = "Кнопка устарела, открываю меню."
ERROR = "⚠️ Что-то пошло не так. Попробуйте ещё раз или нажмите /start."
