import asyncio
from aiogram import Bot, Dispatcher
from src.core.config import config
from src.utils.logger import logger

from src.database.manager import db_manager
from src.bot.middlewares.registration import RegistrationMiddleware
from src.bot.middlewares.force_join import ForceJoinMiddleware
from src.bot.handlers.user import router as user_router
from src.bot.handlers.group_handler import router as group_router
from src.admin.handlers.admin import router as admin_router
from src.bot.middlewares.admin_check import AdminCheckMiddleware

from src.monitoring.alerts import send_admin_alert
from src.monitoring.uptime_monitor import uptime_monitor
from src.pyrogram_client.client import start_pyrogram, stop_pyrogram

from aiohttp import web
import os

async def ping_handler(request):
    """Simple ping handler for UptimeRobot and Render health checks."""
    return web.Response(text="Bot is running! 🚀", status=200)

async def start_web_server():
    """Starts a lightweight web server for keep-alive pings."""
    app = web.Application()
    app.router.add_get('/', ping_handler)
    app.router.add_get('/ping', ping_handler)
    
    # Render assigns a port dynamically
    port = int(os.environ.get("PORT", 8080))
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    logger.info(f"Web server started on port {port} for keep-alive pings.")

async def main():
    """Application bootstrap."""
    
    logger.info("Starting checker-bot...")
    
    # Start web server for Render
    await start_web_server()
    
    # Initialize database
    await db_manager.init_db()
    
    # Initialize Pyrogram
    await start_pyrogram()
    
    # Initialize bot and dispatcher
    bot = Bot(token=config.BOT_TOKEN)
    dp = Dispatcher()
    
    # Register Middlewares
    dp.update.outer_middleware(RegistrationMiddleware())
    dp.update.outer_middleware(ForceJoinMiddleware())
    
    # Register Admin Middleware to the admin router only
    admin_router.message.middleware(AdminCheckMiddleware())
    admin_router.callback_query.middleware(AdminCheckMiddleware())
    
    # Include Routers
    dp.include_router(user_router)
    dp.include_router(group_router)
    dp.include_router(admin_router)
    
    # Startup Alert
    await send_admin_alert(bot, "Bot started successfully! 🚀")
    
    try:
        logger.info("Bot is polling...")
        # Explicitly allow edited_message updates
        await dp.start_polling(
            bot, 
            allowed_updates=["message", "edited_message", "callback_query", "chat_member"]
        )
    except Exception as e:
        logger.error(f"Critical error during polling: {e}")
        await send_admin_alert(bot, f"Critical error during polling: `{e}`")
    finally:
        logger.info("Closing sessions...")
        uptime = uptime_monitor.get_uptime()
        await send_admin_alert(bot, f"Bot is shutting down. 🛑\nUptime: `{uptime}`")
        
        await stop_pyrogram()
        await bot.session.close()
        await db_manager.close()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user.")
    except Exception as e:
        logger.critical(f"Unexpected error: {e}")
