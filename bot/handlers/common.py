from datetime import datetime

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.types import CallbackQuery, Message

from bot import texts
from bot.config import BOOKING_DAYS, Config
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


async def welcome_text(user_id: int, name: str, db: Database, config: Config, notice: str = "") -> str:
    """Приветствие с ближайшей записью клиента, если она есть."""
    upcoming = await db.get_user_appointments(user_id, datetime.now(config.timezone))
    return texts.welcome(name, upcoming[0] if upcoming else None, notice)


@router.message(CommandStart())
async def cmd_start(message: Message, db: Database, config: Config) -> None:
    user = message.from_user
    await message.answer(await welcome_text(user.id, user.first_name, db, config), reply_markup=kb.main_menu())


@router.message(Command("admin"))
async def cmd_admin_denied(message: Message) -> None:
    # Сюда попадают только не-админы: админский роутер подключён раньше
    await message.answer(texts.ADMIN_ONLY)


async def show_main(callback: CallbackQuery, db: Database, config: Config, notice: str = "") -> None:
    user = callback.from_user
    await render(callback, await welcome_text(user.id, user.first_name, db, config, notice), kb.main_menu())


@router.callback_query(MenuCb.filter(F.action == "main"))
async def on_main(callback: CallbackQuery, db: Database, config: Config) -> None:
    await show_main(callback, db, config)


# services и contacts — кнопки из сообщений прошлой версии
@router.callback_query(MenuCb.filter(F.action.in_({"about", "services", "contacts"})))
async def show_about(callback: CallbackQuery, db: Database) -> None:
    await render(callback, texts.about(await db.get_services()), kb.about())


@router.callback_query(NoopCb.filter())
async def noop(callback: CallbackQuery, callback_data: NoopCb) -> None:
    alert = NOOP_ALERTS.get(callback_data.reason)
    if alert:
        await notify(callback, alert)
