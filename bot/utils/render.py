import logging
from contextlib import suppress

from aiogram.exceptions import TelegramAPIError, TelegramBadRequest
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message

logger = logging.getLogger(__name__)


async def render(callback: CallbackQuery, text: str, markup: InlineKeyboardMarkup | None = None) -> None:
    """Показывает экран, редактируя сообщение с кнопкой.

    Если сообщение отредактировать нельзя (слишком старое или удалено),
    отправляет новое, чтобы клиент не остался без ответа.
    """
    message = callback.message
    if isinstance(message, Message):
        try:
            await message.edit_text(text, reply_markup=markup)
            return
        except TelegramBadRequest as e:
            if "message is not modified" in str(e):
                return
            logger.info("Не удалось отредактировать сообщение, отправляю новое: %s", e)
    await callback.bot.send_message(callback.from_user.id, text, reply_markup=markup)


async def notify(callback: CallbackQuery, text: str, alert: bool = False) -> None:
    """Всплывающее уведомление. На одно нажатие Telegram принимает только один ответ,
    поэтому повторную попытку тихо пропускаем."""
    with suppress(TelegramAPIError):
        await callback.answer(text, show_alert=alert)
