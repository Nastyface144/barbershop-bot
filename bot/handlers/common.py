from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.types import CallbackQuery, Message

from bot import texts
from bot.config import BOOKING_DAYS
from bot.database import Database
from bot.keyboards import client as kb
from bot.keyboards.callbacks import MenuCb, NoopCb
from bot.utils.formatting import plural
from bot.utils.render import notify, render

router = Router(name="common")

NOOP_ALERTS = {
    "past": "Эта дата уже прошла.",
    "full": "На этот день записи нет.",
    "far": f"Запись открыта на {BOOKING_DAYS} {plural(BOOKING_DAYS, ('день', 'дня', 'дней'))} вперёд.",
}


@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    await message.answer(texts.welcome(message.from_user.first_name), reply_markup=kb.main_menu())


@router.message(Command("admin"))
async def cmd_admin_denied(message: Message) -> None:
    # Сюда попадают только не-админы: админский роутер подключён раньше
    await message.answer(texts.ADMIN_ONLY)


@router.callback_query(MenuCb.filter(F.action == "main"))
async def show_main(callback: CallbackQuery) -> None:
    await render(callback, texts.welcome(callback.from_user.first_name), kb.main_menu())


@router.callback_query(MenuCb.filter(F.action == "services"))
async def show_services(callback: CallbackQuery, db: Database) -> None:
    services = await db.get_services()
    await render(callback, texts.services_and_prices(services), kb.services_info())


@router.callback_query(MenuCb.filter(F.action == "contacts"))
async def show_contacts(callback: CallbackQuery) -> None:
    await render(callback, texts.contacts(), kb.contacts())


@router.callback_query(NoopCb.filter())
async def noop(callback: CallbackQuery, callback_data: NoopCb) -> None:
    alert = NOOP_ALERTS.get(callback_data.reason)
    if alert:
        await notify(callback, alert)
