"""Тексты экранов бота."""
from datetime import date, timedelta
from html import escape

from bot import demo_data
from bot.config import MAX_ACTIVE_BOOKINGS, PAYMENT_TIMEOUT_MIN
from bot.database import Appointment, Master, Service
from bot.utils.formatting import (
    client_label,
    fmt_date,
    fmt_duration,
    fmt_price,
    fmt_time,
    plural,
)

TOTAL_STEPS = 4


def welcome(name: str, notice: str = "") -> str:
    head = f"{notice}\n\n" if notice else ""
    return (
        f"{head}💈 <b>{escape(demo_data.SHOP_NAME)}</b>\n\n"
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


def confirm(service: Service, master: Master, day: date, start: int, online: bool) -> str:
    details = _details(service.name, master.name, day, start, start + service.duration, service.price)
    question = "Как удобнее оплатить?" if online else f"{PAY_IN_SALON}\n\nВсё верно?"
    return f"📝 <b>Проверьте запись</b>\n\n{details}\n\n{question}"


PAY_IN_SALON = "💵 Оплата в салоне: наличными или картой."
PAID_ONLINE = "💳 Оплачено онлайн."


def _payment_line(a: Appointment) -> str:
    if a.paid:
        return PAID_ONLINE
    return PAY_IN_SALON


def _payment_mark(a: Appointment) -> str:
    """Короткая пометка об оплате для списков."""
    return "💳 оплачено" if a.paid else "💵 в салоне"


def booked(a: Appointment) -> str:
    details = _details(a.service_name, a.master_name, a.day, a.start_min, a.end_min, a.price)
    return (
        f"✅ <b>Вы записаны!</b>\n\n{details}\n{_payment_line(a)}\n\n"
        f"📍 {escape(demo_data.SHOP_ADDRESS)}\n\n"
        "Напомним о визите за сутки и за 2 часа. Ждём вас!\n\n"
        "Что-то ещё? 👇"
    )


SLOT_TAKEN = "😔 Это время только что заняли. Выберите другое."
BOOKING_OVERLAP = "У вас уже есть запись на это время. Выберите другое."
BOOKING_LIMIT = (
    f"У вас уже {MAX_ACTIVE_BOOKINGS} {plural(MAX_ACTIVE_BOOKINGS, ('активная запись', 'активные записи', 'активных записей'))}. "
    "Отмените одну из них, чтобы записаться снова."
)
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
            f"✂️ {escape(a.service_name)} — {fmt_price(a.price)} · {_payment_mark(a)}\n"
            f"👤 Мастер: {escape(a.master_name)}"
        )
    return "\n".join(lines)


def cancel_confirm(a: Appointment) -> str:
    details = _details(a.service_name, a.master_name, a.day, a.start_min, a.end_min, a.price)
    text = f"❓ <b>Отменить запись?</b>\n\n{details}"
    if a.paid:
        text += "\n\n💳 Запись оплачена онлайн — салон свяжется с вами, чтобы вернуть деньги."
    return text


# --- Онлайн-оплата ---


def awaiting_payment(a: Appointment) -> str:
    details = _details(a.service_name, a.master_name, a.day, a.start_min, a.end_min, a.price)
    return (
        f"💳 <b>Оплата записи</b>\n\n{details}\n\n"
        f"Счёт отправлен ниже 👇 Время закреплено за вами на {PAYMENT_TIMEOUT_MIN} минут — "
        "если не оплатить, оно освободится."
    )


def invoice_title() -> str:
    return demo_data.SHOP_NAME[:32]


def invoice_description(a: Appointment) -> str:
    return f"{a.service_name} · мастер {a.master_name} · {fmt_date(a.day)}, {fmt_time(a.start_min)}"[:255]


PAYMENT_UNAVAILABLE = "Онлайн-оплата сейчас недоступна. Выберите оплату в салоне."
PAYMENT_EXPIRED_ALERT = "Время на оплату истекло. Запишитесь заново."
PAYMENT_EXPIRED = "⏳ Время на оплату истекло, и запись не создана. Время снова свободно — можно записаться ещё раз."
PAID_BUT_TAKEN = (
    "😔 Оплата прошла, но время уже занято. Салон свяжется с вами, чтобы вернуть деньги "
    "или подобрать другое время."
)


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
        f"🗓 {fmt_date(a.day)}, {fmt_time(a.start_min)}–{fmt_time(a.end_min)}\n"
        f"{_payment_line(a)}"
    )


REFUND_NOTE = "\n\n⚠️ Запись была оплачена онлайн — верните деньги клиенту."


def admin_new_booking(a: Appointment) -> str:
    return f"🆕 <b>Новая запись</b>\n\n{_admin_details(a)}"


def admin_cancelled(a: Appointment) -> str:
    return f"❌ <b>Клиент отменил запись</b>\n\n{_admin_details(a)}" + (REFUND_NOTE if a.paid else "")


def admin_paid_but_taken(a: Appointment) -> str:
    return (
        f"⚠️ <b>Оплата пришла, но время уже занято</b>\n\n{_admin_details(a)}\n\n"
        "Клиент оплатил после того, как бронь истекла и время заняли. "
        "Свяжитесь с клиентом: верните деньги или предложите другое время."
    )


def admin_cancelled_by_admin(a: Appointment, admin_name: str) -> str:
    return f"❌ <b>Запись отменена администратором</b> ({escape(admin_name)})\n\n{_admin_details(a)}" + (
        REFUND_NOTE if a.paid else ""
    )


def admin_panel(today_count: int, tomorrow_count: int, notice: str = "") -> str:
    head = f"{notice}\n\n" if notice else ""
    return (
        f"{head}🛠 <b>Панель администратора</b>\n\n"
        f"📅 Сегодня: <b>{today_count}</b> {_records_word(today_count)}\n"
        f"📅 Завтра: <b>{tomorrow_count}</b> {_records_word(tomorrow_count)}"
    )


def admin_day(
    day: date,
    label: str,
    appointments: list[Appointment],
    salon_closed: bool,
    masters_off: list[str],
    total: int,
    notice: str = "",
) -> str:
    title = f"{label}, {fmt_date(day)}" if label else fmt_date(day).capitalize()
    head = f"{notice}\n\n" if notice else ""
    head += f"📅 <b>{title}</b>"
    if salon_closed:
        head += "\n🔒 Салон закрыт для записи"
    for name in masters_off:
        head += f"\n🔒 {escape(name)} не принимает"
    if not appointments:
        return f"{head}\n\nЗаписей нет."
    head += f"\n{len(appointments)} {_records_word(len(appointments))} на {fmt_price(total)}"
    text = head
    for shown, a in enumerate(appointments):
        block = (
            f"\n\n<b>{fmt_time(a.start_min)}–{fmt_time(a.end_min)}</b> · {escape(a.master_name)}\n"
            f"✂️ {escape(a.service_name)} — {fmt_price(a.price)} · {_payment_mark(a)}\n"
            f"👤 {client_label(a.client_name, a.username)}"
        )
        if len(text) + len(block) > MESSAGE_LIMIT:
            rest = len(appointments) - shown
            return f"{text}\n\n…и ещё {rest} {_records_word(rest)}"
        text += block
    return text


# Telegram ограничивает сообщение 4096 символами — оставляем запас
MESSAGE_LIMIT = 3900


def admin_digest(report: str) -> str:
    return f"☀️ <b>Доброе утро! План на сегодня</b>\n\n{report}"


def admin_cancel_confirm(a: Appointment) -> str:
    return (
        f"❓ <b>Отменить запись клиента?</b>\n\n{_admin_details(a)}\n\n"
        "Клиент получит сообщение об отмене."
    ) + (REFUND_NOTE if a.paid else "")


def admin_cancelled_notice(delivered: bool) -> str:
    if delivered:
        return "✅ Запись отменена, клиент получил уведомление."
    return "✅ Запись отменена. ⚠️ Уведомить клиента не удалось — свяжитесь с ним сами."


def cancelled_by_salon(a: Appointment) -> str:
    details = _details(a.service_name, a.master_name, a.day, a.start_min, a.end_min, a.price)
    return (
        f"😔 <b>Запись отменена салоном</b>\n\n{details}\n\n"
        + ("💳 Деньги за онлайн-оплату вернём — салон свяжется с вами.\n\n" if a.paid else "")
        + "Приносим извинения! Выберите другое удобное время — это займёт минуту."
    )


def admin_calendar(action: str) -> str:
    if action == "day":
        return (
            "🗓 <b>Записи на другую дату</b>\n\n"
            "Выберите дату.\n"
            "🔒 — салон закрыт, • — есть закрытое время."
        )
    return (
        "🔒 <b>Закрыть день или время</b>\n\n"
        "Выберите дату.\n"
        "🔒 — салон закрыт, • — есть закрытое время."
    )


def admin_manage_day(
    day: date, scope: str, closed: bool, salon_closed: bool, appointments_count: int
) -> str:
    text = f"🗓 <b>{fmt_date(day)}</b>\nНастраиваете: <b>{escape(scope)}</b>\n\n"
    if salon_closed and not closed:
        return text + "🔒 Весь салон закрыт в этот день. Откройте его во вкладке «🏠 Салон»."
    text += f"Статус: {'🔒 закрыт' if closed else '🟢 открыт'}\nЗаписей: {appointments_count}\n\n"
    if closed:
        text += "Откройте день, чтобы клиенты снова могли записаться."
    else:
        text += (
            "Нажмите на время, чтобы закрыть или открыть его.\n"
            "🔒 — закрыто, 👤 — есть запись"
        )
        if scope != SALON_SCOPE:
            text += ", 🏠 — закрыто для всего салона"
        text += "."
    if appointments_count:
        text += "\n\n⚠️ Закрытие не отменяет созданные записи — их можно отменить в списке записей."
    return text


SALON_SCOPE = "весь салон"
SLOT_CLOSED_FOR_SALON = "Это время закрыто для всего салона. Откройте его во вкладке «🏠 Салон»."


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
