import logging

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError

from bot.config import Config

logger = logging.getLogger(__name__)


async def notify_admins(bot: Bot, config: Config, text: str) -> None:
    """Отправляет уведомление всем администраторам. Ошибки не прерывают работу клиента."""
    for admin_id in config.admin_ids:
        try:
            await bot.send_message(admin_id, text)
        except TelegramAPIError as e:
            logger.warning("Не удалось уведомить администратора %s: %s", admin_id, e)
