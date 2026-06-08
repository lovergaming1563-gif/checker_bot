from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from src.database.models import Service

def get_services_keyboard(services: list[Service]) -> InlineKeyboardMarkup:
    """Generates a dynamic keyboard for active services."""
    builder = InlineKeyboardBuilder()
    
    # Add Super Check button at the top always
    builder.row(InlineKeyboardButton(text="🌐 SUPER CHECK (ALL)", callback_data="super_check"))
    
    for service in services:
        builder.button(
            text=f"🔍 {service.name.upper()}",
            callback_data=f"service_{service.id}"
        )
    
    builder.adjust(1, 2) # Adjust layout: 1 for Super Check, then 2 per row
    
    # Add a global cancel/close button at the bottom
    builder.row(
        InlineKeyboardButton(text="❌ CANCEL", callback_data="cancel_request")
    )
    
    return builder.as_markup()

def get_cancel_keyboard() -> InlineKeyboardMarkup:
    """Simple keyboard with just a cancel button."""
    builder = InlineKeyboardBuilder()
    builder.button(text="❌ CANCEL", callback_data="cancel_request")
    return builder.as_markup()
