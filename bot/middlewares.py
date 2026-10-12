from collections.abc import Awaitable, Callable
from contextlib import suppress
from typing import Any

from aiogram import BaseMiddleware
from aiogram.exceptions import TelegramAPIError
from aiogram.types import CallbackQuery


class CallbackAnswerMiddleware(BaseMiddleware):
    """Гарантирует ответ на каждое нажатие кнопки, чтобы у клиента не висели «часики».

    Если обработчик уже ответил сам (например, всплывающим сообщением),
    повторный ответ Telegram отклонит — эту ошибку просто игнорируем.
    """

    async def __call__(
        self,
        handler: Callable[[CallbackQuery, dict[str, Any]], Awaitable[Any]],
        event: CallbackQuery,
        data: dict[str, Any],
    ) -> Any:
        try:
            return await handler(event, data)
        finally:
            with suppress(TelegramAPIError):
                await event.answer()
