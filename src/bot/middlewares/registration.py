from typing import Any, Awaitable, Callable, Dict
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, User as TgUser
from src.database.manager import db_manager

from aiogram.types import TelegramObject, User as TgUser, Message, CallbackQuery

class RegistrationMiddleware(BaseMiddleware):
    """Middleware to automatically register users and enforce global bans."""
    
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        user: TgUser = data.get("event_from_user")
        
        if user and not user.is_bot:
            # Register or update user
            db_user = await db_manager.get_or_create_user(
                tg_id=user.id,
                first_name=user.first_name,
                username=user.username
            )
            
            # Enforce Ban
            if db_user.is_banned:
                ban_msg = "🚫 Your access to this bot has been restricted."
                if isinstance(event, Message):
                    await event.answer(ban_msg)
                elif isinstance(event, CallbackQuery):
                    await event.answer(ban_msg, show_alert=True)
                return # Block further processing
            
            # Inject database user object into the handler data
            data["db_user"] = db_user
        
        return await handler(event, data)
