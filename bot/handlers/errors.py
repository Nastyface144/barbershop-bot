import logging

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError
from aiogram.types import ErrorEvent

from bot import texts

logger = logging.getLogger(__name__)


async def error_handler(event: ErrorEvent, bot: Bot) -> bool:
    """Логирует любую ошибку в обработчике и вежливо сообщает о ней пользователю."""
    logger.exception("Ошибка при обработке апдейта %s", event.update.update_id, exc_info=event.exception)

    update = event.update
    user = None
    if update.callback_query:
        user = update.callback_query.from_user
    elif update.message:
        user = update.message.from_user

    if user is not None:
        try:
            await bot.send_message(user.id, texts.ERROR)
        except TelegramAPIError:
            pass
    return True
