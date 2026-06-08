from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardMarkup
from src.database.models import Service

def get_admin_main_keyboard() -> InlineKeyboardMarkup:
    """Main admin dashboard menu."""
    builder = InlineKeyboardBuilder()
    builder.button(text="📊 Refresh Stats", callback_data="admin_stats")
    builder.button(text="🛠 Manage Services", callback_data="admin_services")
    builder.button(text="👤 Manage Users", callback_data="admin_users")
    builder.button(text="📢 Broadcast", callback_data="admin_broadcast")
    builder.button(text="📦 Bulk Check", callback_data="admin_bulk_check")
    builder.adjust(1)
    return builder.as_markup()

def get_bulk_services_keyboard(services: list[Service]) -> InlineKeyboardMarkup:
    """Keyboard listing all active services for bulk checking."""
    builder = InlineKeyboardBuilder()
    
    for service in services:
        if service.is_active:
            builder.button(
                text=f"🔍 {service.name}",
                callback_data=f"bulk_service_{service.id}"
            )
    
    builder.button(text="🔙 Back", callback_data="admin_main")
    builder.adjust(1)
    return builder.as_markup()

def get_services_mgmt_keyboard(services: list[Service]) -> InlineKeyboardMarkup:
    """Keyboard listing all services for management."""
    builder = InlineKeyboardBuilder()
    
    for service in services:
        status_icon = "✅" if service.is_active else "❌"
        builder.button(
            text=f"{status_icon} {service.name}",
            callback_data=f"mgmt_service_{service.id}"
        )
    
    builder.button(text="➕ Add New Service", callback_data="admin_add_service")
    builder.button(text="🔙 Back", callback_data="admin_main")
    builder.adjust(1)
    return builder.as_markup()

def get_service_edit_keyboard(service_id: int, is_active: bool) -> InlineKeyboardMarkup:
    """Actions for a specific service."""
    builder = InlineKeyboardBuilder()
    
    toggle_text = "🔴 Disable Service" if is_active else "🟢 Enable Service"
    builder.button(text=toggle_text, callback_data=f"toggle_service_{service_id}")
    builder.button(text="📝 Rename", callback_data=f"rename_service_{service_id}")
    builder.button(text="🆔 Change Group ID", callback_data=f"chgroup_service_{service_id}")
    builder.button(text="💬 Change Reply ID", callback_data=f"chreply_service_{service_id}")
    builder.button(text="🗑 Delete Service", callback_data=f"delete_service_{service_id}")
    builder.button(text="🔙 Back", callback_data="admin_services")
    
    builder.adjust(1)
    return builder.as_markup()

def get_user_mgmt_keyboard(telegram_id: int, is_banned: bool) -> InlineKeyboardMarkup:
    """Actions for a specific user."""
    builder = InlineKeyboardBuilder()
    
    ban_text = "🔓 Unban User" if is_banned else "🚫 Ban User"
    builder.button(text=ban_text, callback_data=f"toggle_ban_{telegram_id}")
    builder.button(text="🔙 Back", callback_data="admin_users")
    builder.adjust(1)
    return builder.as_markup()
