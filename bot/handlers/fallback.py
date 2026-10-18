"""Ответы на всё, что не обработали другие роутеры. Подключается последним."""
from aiogram import Router
from aiogram.types import CallbackQuery, Message

from bot import texts
from bot.config import Config
from bot.database import Database
from bot.handlers.common import show_main
from bot.keyboards import client as kb
from bot.utils.render import notify

router = Router(name="fallback")


@router.message()
async def unknown_message(message: Message) -> None:
    await message.answer(texts.UNKNOWN_MESSAGE, reply_markup=kb.main_menu())


@router.callback_query()
async def unknown_callback(callback: CallbackQuery, db: Database, config: Config) -> None:
    await notify(callback, texts.STALE_BUTTON)
    await show_main(callback, db, config)
