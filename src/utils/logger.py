import logging
import sys
from src.core.config import config

def setup_logger():
    """Configures centralized logging for the application."""
    
    # Define log format
    log_format = (
        "%(asctime)s | %(levelname)-8s | %(name)s:%(funcName)s:%(lineno)d - %(message)s"
    )
    
    # Set the base logging level
    level = getattr(logging, config.LOG_LEVEL.upper(), logging.INFO)
    
    # Configure root logger
    logging.basicConfig(
        level=level,
        format=log_format,
        handlers=[
            logging.StreamHandler(sys.stdout)
        ]
    )
    
    # Set levels for noisy libraries
    logging.getLogger("aiogram").setLevel(logging.INFO)
    
    logger = logging.getLogger("checker-bot")
    logger.info(f"Logging initialized with level: {config.LOG_LEVEL}")
    
    return logger

# Initialize logger instance
logger = setup_logger()
