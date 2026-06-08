import logging
from aiogram import Bot
from src.database.manager import db_manager
from sqlalchemy import text

logger = logging.getLogger("checker-bot.monitoring")

async def check_database_health() -> bool:
    """Verifies that the database is reachable and responsive."""
    try:
        async with db_manager.get_session() as session:
            await session.execute(text("SELECT 1"))
        return True
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        return False

async def check_telegram_api(bot: Bot) -> bool:
    """Verifies connectivity with the Telegram Bot API."""
    try:
        await bot.get_me()
        return True
    except Exception as e:
        logger.error(f"Telegram API health check failed: {e}")
        return False
