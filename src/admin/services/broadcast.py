import asyncio
from aiogram import Bot
from aiogram.exceptions import TelegramForbiddenError, TelegramRetryAfter
from src.database.manager import db_manager
from src.utils.logger import logger

async def send_broadcast(bot: Bot, text: str) -> dict:
    """
    Sends a message to all registered non-banned users.
    Returns statistics of the broadcast.
    """
    users = await db_manager.get_all_users()
    total_users = len(users)
    success_count = 0
    failed_count = 0
    blocked_count = 0

    logger.info(f"Starting broadcast to {total_users} users.")

    for user in users:
        try:
            await bot.send_message(chat_id=user.telegram_id, text=text)
            success_count += 1
            # Avoid hitting rate limits
            await asyncio.sleep(0.05) 
            
        except TelegramForbiddenError:
            blocked_count += 1
            logger.warning(f"User {user.telegram_id} has blocked the bot.")
            
        except TelegramRetryAfter as e:
            logger.warning(f"Rate limit hit. Retrying after {e.retry_after} seconds.")
            await asyncio.sleep(e.retry_after)
            # Retry once
            try:
                await bot.send_message(chat_id=user.telegram_id, text=text)
                success_count += 1
            except Exception:
                failed_count += 1
                
        except Exception as e:
            failed_count += 1
            logger.error(f"Failed to send broadcast to {user.telegram_id}: {e}")

    logger.info(f"Broadcast finished. Success: {success_count}, Blocked: {blocked_count}, Failed: {failed_count}")
    
    return {
        "total": total_users,
        "success": success_count,
        "blocked": blocked_count,
        "failed": failed_count
    }
