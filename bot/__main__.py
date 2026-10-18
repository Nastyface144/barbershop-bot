import asyncio
import logging
import sys

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramAPIError, TelegramNetworkError, TelegramUnauthorizedError
from aiogram.types import BotCommand, BotCommandScopeChat, BotCommandScopeDefault

from bot import texts
from bot.config import Config, ConfigError, load_config
from bot.database import Database
from bot.handlers import get_routers
from bot.handlers.errors import error_handler
from bot.middlewares import CallbackAnswerMiddleware
from bot.scheduler import setup_scheduler

logger = logging.getLogger("bot")


async def set_profile(bot: Bot) -> None:
    """Описание бота в пустом чате и в профиле."""
    try:
        await bot.set_my_description(texts.BOT_DESCRIPTION)
        await bot.set_my_short_description(texts.BOT_SHORT_DESCRIPTION)
    except TelegramAPIError as e:
        logger.warning("Не удалось обновить описание бота: %s", e)


async def set_commands(bot: Bot, config: Config) -> None:
    client_commands = [BotCommand(command="start", description="Главное меню")]
    await bot.set_my_commands(client_commands, scope=BotCommandScopeDefault())
    for admin_id in config.admin_ids:
        try:
            await bot.set_my_commands(
                client_commands + [BotCommand(command="admin", description="Панель администратора")],
                scope=BotCommandScopeChat(chat_id=admin_id),
            )
        except TelegramAPIError as e:
            logger.warning("Не удалось задать команды для админа %s: %s (он ещё не писал боту?)", admin_id, e)


async def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-7s | %(name)s: %(message)s",
    )

    try:
        config = load_config()
    except ConfigError as e:
        logger.error("%s", e)
        sys.exit(1)
    if not config.admin_ids:
        logger.warning("ADMIN_ID не задан — уведомления и /admin будут недоступны")

    db = Database(config.db_path)
    await db.connect()

    bot = Bot(
        token=config.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML, link_preview_is_disabled=True),
    )
    dp = Dispatcher(db=db, config=config)
    dp.callback_query.middleware(CallbackAnswerMiddleware())
    dp.include_routers(*get_routers())
    dp.errors.register(error_handler)

    scheduler = setup_scheduler(bot, db, config)

    try:
        await set_commands(bot, config)
        await set_profile(bot)
        await bot.delete_webhook(drop_pending_updates=True)
        scheduler.start()
        me = await bot.get_me()
        logger.info("Бот @%s запущен", me.username)
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    except TelegramUnauthorizedError:
        logger.error("Telegram отклонил BOT_TOKEN. Проверьте токен в файле .env")
    except TelegramNetworkError as e:
        logger.error("Нет связи с Telegram: %s", e)
    finally:
        if scheduler.running:
            scheduler.shutdown(wait=False)
        await db.close()
        await bot.session.close()
        logger.info("Бот остановлен")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        pass
