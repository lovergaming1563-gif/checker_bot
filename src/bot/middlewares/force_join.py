from typing import Any, Awaitable, Callable, Dict
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from src.core.config import config
from src.utils.logger import logger

class ForceJoinMiddleware(BaseMiddleware):
    """Middleware to enforce channel membership."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        # Skip check if no channel configured
        if not config.FORCE_JOIN_CHANNEL:
            return await handler(event, data)

        user = data.get("event_from_user")
        if not user or user.is_bot:
            return await handler(event, data)

        # Remove admin bypass so everyone must join (good for testing too)

        # Check membership
        is_joined = False
        try:
            bot = data.get("bot")
            member = await bot.get_chat_member(chat_id=config.FORCE_JOIN_CHANNEL, user_id=user.id)
            
            # Statuses that count as "joined"
            is_joined = member.status in ["member", "administrator", "creator"]
            
        except Exception as e:
            logger.error(f"Error checking membership for {user.id} in {config.FORCE_JOIN_CHANNEL}: {e}")
            # If bot is not admin or user hasn't joined, it throws an error.
            # We must assume they haven't joined to enforce the rule.
            is_joined = False

        if not is_joined:
            # Prepare join message
            channel_url = f"https://t.me/{config.FORCE_JOIN_CHANNEL.replace('@', '')}"
            text = (
                "🚨 *ACCESS RESTRICTED* 🚨\n\n"
                "You must join our updates channel to use this bot. This helps us keep you informed about service status.\n\n"
                "1. Click the button below to join.\n"
                "2. After joining, click *'Verify Join'*."
            )
            
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="📢 JOIN CHANNEL", url=channel_url)],
                [InlineKeyboardButton(text="✅ VERIFY JOIN", callback_data="check_join")]
            ])

            # Extract actual event if it's an Update
            actual_event = event
            if hasattr(event, "message") and event.message:
                actual_event = event.message
            elif hasattr(event, "callback_query") and event.callback_query:
                actual_event = event.callback_query

            if isinstance(actual_event, Message):
                await actual_event.answer(text, reply_markup=keyboard, parse_mode="Markdown")
            elif isinstance(actual_event, CallbackQuery):
                # Always answer the callback first to stop the loading spinner
                try:
                    await actual_event.answer()
                except:
                    pass
                    
                if actual_event.data == "check_join":
                    await actual_event.answer("⚠️ You haven't joined yet! Please join the channel first.", show_alert=True)
                else:
                    await actual_event.message.answer(text, reply_markup=keyboard, parse_mode="Markdown")
            
            return # Block execution

        return await handler(event, data)
