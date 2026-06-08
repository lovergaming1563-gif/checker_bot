from typing import Any, Awaitable, Callable, Dict
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, User
from src.database.manager import db_manager

class AdminCheckMiddleware(BaseMiddleware):
    """Middleware to check if the user has admin privileges for admin-scoped handlers."""
    
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        user: User = data.get("event_from_user")
        
        if not user:
            return await handler(event, data)

        # Check if user is an admin
        is_admin = await db_manager.is_admin(user.id)
        
        if is_admin:
            return await handler(event, data)
        
        # If not an admin and trying to access an admin handler, ignore or notify
        # (Usually better to just ignore to avoid bot discovery by unauthorized users)
        return None
