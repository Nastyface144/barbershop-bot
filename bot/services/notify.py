import logging

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError

from bot.config import Config

logger = logging.getLogger(__name__)


async def notify_admins(bot: Bot, config: Config, text: str, exclude: int | None = None) -> None:
    """Отправляет уведомление всем администраторам, кроме `exclude`. Ошибки не прерывают работу."""
    for admin_id in config.admin_ids:
        if admin_id == exclude:
            continue
        try:
            await bot.send_message(admin_id, text)
        except TelegramAPIError as e:
            logger.warning("Не удалось уведомить администратора %s: %s", admin_id, e)
