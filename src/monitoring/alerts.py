from aiogram import Bot
from src.core.config import config
from src.utils.logger import logger

async def send_admin_alert(bot: Bot, message: str):
    """Sends a notification message to all configured administrators."""
    for admin_id in config.ADMIN_IDS:
        try:
            await bot.send_message(
                chat_id=admin_id,
                text=f"🚨 *SYSTEM ALERT*\n\n{message}",
                parse_mode="Markdown"
            )
        except Exception as e:
            logger.error(f"Failed to send alert to admin {admin_id}: {e}")
