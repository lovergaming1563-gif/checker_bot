from pyrogram import Client
from src.core.config import config
from src.utils.logger import logger
from typing import Optional

class PyrogramManager:
    """Manages the lifecycle of the Pyrogram user client."""
    
    def __init__(self):
        self._client: Optional[Client] = None

    def get_client(self) -> Client:
        """Returns the Pyrogram client instance."""
        if self._client is None:
            if not all([config.PYROGRAM_API_ID, config.PYROGRAM_API_HASH, config.PYROGRAM_SESSION_STRING]):
                logger.warning("Pyrogram credentials incomplete. Client will not start.")
                return None
            
            self._client = Client(
                name="checker_user",
                api_id=config.PYROGRAM_API_ID,
                api_hash=config.PYROGRAM_API_HASH,
                session_string=config.PYROGRAM_SESSION_STRING,
                in_memory=True
            )
        return self._client

    async def start(self):
        """Starts the Pyrogram client."""
        client = self.get_client()
        if client:
            try:
                await client.start()
                logger.info("Pyrogram client started successfully")
            except Exception as e:
                logger.error(f"Failed to start Pyrogram client: {e}")

    async def stop(self):
        """Stops the Pyrogram client."""
        if self._client:
            try:
                await self._client.stop()
                logger.info("Pyrogram client stopped successfully")
            except Exception as e:
                logger.error(f"Error stopping Pyrogram client: {e}")

# Singleton instance
pyro_manager = PyrogramManager()

async def start_pyrogram():
    await pyro_manager.start()

async def stop_pyrogram():
    await pyro_manager.stop()

def get_pyrogram_client() -> Optional[Client]:
    return pyro_manager.get_client()
