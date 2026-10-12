"""Ответы на всё, что не обработали другие роутеры. Подключается последним."""
from aiogram import Router
from aiogram.types import CallbackQuery, Message

from bot import texts
from bot.keyboards import client as kb
from bot.utils.render import notify, render

router = Router(name="fallback")


@router.message()
async def unknown_message(message: Message) -> None:
    await message.answer(texts.UNKNOWN_MESSAGE, reply_markup=kb.main_menu())


@router.callback_query()
async def unknown_callback(callback: CallbackQuery) -> None:
    await notify(callback, texts.STALE_BUTTON)
    await render(callback, texts.welcome(callback.from_user.first_name), kb.main_menu())
