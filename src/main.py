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

from aiohttp import web, ClientSession
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

async def self_ping_task():
    """Background task to ping itself to keep Render alive."""
    url = os.environ.get("RENDER_EXTERNAL_URL")
    if not url:
        logger.info("RENDER_EXTERNAL_URL not set, skipping self-ping.")
        return

    logger.info(f"Starting self-ping task for {url}")
    while True:
        try:
            async with ClientSession() as session:
                async with session.get(url) as response:
                    if response.status == 200:
                        logger.debug("Self-ping successful.")
                    else:
                        logger.warning(f"Self-ping failed with status: {response.status}")
        except Exception as e:
            logger.error(f"Error during self-ping: {e}")
        
        # Ping every 10 minutes
        await asyncio.sleep(600)

async def main():
    """Application bootstrap."""
    
    logger.info("Starting checker-bot...")
    
    # 1. Start web server IMMEDIATELY for Render port binding
    await start_web_server()
    
    # 2. Start self-ping background task
    asyncio.create_task(self_ping_task())
    
    try:
        # 3. Initialize database
        await db_manager.init_db()
        
        # 4. Initialize Pyrogram
        await start_pyrogram()
        
        # 5. Initialize bot and dispatcher
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
        
        logger.info("Bot is polling...")
        # Explicitly allow edited_message updates
        await dp.start_polling(
            bot, 
            allowed_updates=["message", "edited_message", "callback_query", "chat_member"]
        )
    except Exception as e:
        logger.error(f"Critical error during startup: {e}")
        # Try to send alert if bot was initialized
        try:
            bot = Bot(token=config.BOT_TOKEN)
            await send_admin_alert(bot, f"Critical error during startup: `{e}`")
            await bot.session.close()
        except:
            pass
        raise e
    finally:
        logger.info("Closing sessions...")
        try:
            uptime = uptime_monitor.get_uptime()
            bot = Bot(token=config.BOT_TOKEN)
            await send_admin_alert(bot, f"Bot is shutting down. 🛑\nUptime: `{uptime}`")
            await bot.session.close()
        except:
            pass
        
        await stop_pyrogram()
        await db_manager.close()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user.")
    except Exception as e:
        logger.critical(f"Unexpected error: {e}")
