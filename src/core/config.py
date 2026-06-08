import os
from typing import Optional
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv(override=True)

class Config:
    """Production-ready configuration loader."""
    
    BOT_TOKEN: str = os.getenv("BOT_TOKEN")
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///data/bot.db")
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    FORCE_JOIN_CHANNEL: Optional[str] = os.getenv("FORCE_JOIN_CHANNEL")
    
    # Pyrogram Config
    PYROGRAM_API_ID: Optional[int] = int(os.getenv("PYROGRAM_API_ID")) if os.getenv("PYROGRAM_API_ID") else None
    PYROGRAM_API_HASH: Optional[str] = os.getenv("PYROGRAM_API_HASH")
    PYROGRAM_SESSION_STRING: Optional[str] = os.getenv("PYROGRAM_SESSION_STRING")

    # Parse ADMIN_IDS as a list of integers
    ADMIN_IDS_RAW: str = os.getenv("ADMIN_IDS", "")
    # Handle both commas and spaces
    ADMIN_IDS: list[int] = [
        int(admin_id.strip()) 
        for admin_id in ADMIN_IDS_RAW.replace(",", " ").split() 
        if admin_id.strip().isdigit()
    ]

    @classmethod
    def validate(cls):
        """Validates critical configuration."""
        if not cls.BOT_TOKEN:
            raise ValueError("BOT_TOKEN is not set in environment variables.")
        if not cls.ADMIN_IDS:
            print("Warning: ADMIN_IDS is empty. No admins configured.")

# Initial validation
try:
    Config.validate()
except ValueError as e:
    # We don't exit here to allow for tools/scripts that might not need the bot token
    print(f"Configuration Warning: {e}")

config = Config()
