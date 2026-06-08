from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from typing import Optional, List, Dict, Any, Sequence, Tuple

from src.database.manager import db_manager
from src.admin.keyboards import (
    get_admin_main_keyboard,
    get_services_mgmt_keyboard,
    get_service_edit_keyboard,
    get_user_mgmt_keyboard,
    get_bulk_services_keyboard
)
from src.admin.states import AdminStates
from src.utils.logger import logger
from src.admin.services.broadcast import send_broadcast
from src.admin.services.bulk import process_bulk_batch
from src.utils.validators import validate_mobile_number
import asyncio

import re

router = Router(name="admin_router")

def extract_message_id(link: str) -> Optional[int]:
    """Extracts the message ID from a Telegram message link."""
    if not link or link == "0":
        return None
    
    # Matches /123 or /123/ at the end of the link
    match = re.search(r"/(\d+)/?$", link)
    if match:
        return int(match.group(1))
    return None

async def get_stats_text() -> str:
    """Helper to format dashboard statistics."""
    stats = await db_manager.get_admin_stats()
    return (
        "📊 *Admin Dashboard*\n\n"
        f"👤 Total Users: `{stats['total_users']}`\n"
        f"🛠 Active Services: `{stats['active_services']}`\n\n"
        f"⏳ Pending: `{stats['pending']}`\n"
        f"⚙️ Processing: `{stats['processing']}`\n"
        f"✅ Completed: `{stats['completed']}`\n"
        f"❌ Failed: `{stats['failed']}`\n\n"
        f"📅 Requests Today: `{stats['requests_today']}`"
    )

@router.message(Command("admin"))
async def cmd_admin(message: Message, state: FSMContext):
    """Entry point for the admin panel."""
    await state.clear()
    text = await get_stats_text()
    await message.answer(text, parse_mode="Markdown", reply_markup=get_admin_main_keyboard())

@router.callback_query(F.data == "admin_stats")
async def refresh_stats(callback: CallbackQuery):
    """Refreshes the dashboard stats."""
    text = await get_stats_text()
    await callback.message.edit_text(text, parse_mode="Markdown", reply_markup=get_admin_main_keyboard())
    await callback.answer("Stats updated!")

# --- Service Management ---

@router.callback_query(F.data == "admin_services")
async def list_services(callback: CallbackQuery):
    """Shows the list of all services."""
    services = await db_manager.get_all_services()
    await callback.message.edit_text(
        "🛠 *Service Management*\nSelect a service to edit or add a new one:",
        parse_mode="Markdown",
        reply_markup=get_services_mgmt_keyboard(list(services))
    )
    await callback.answer()

@router.callback_query(F.data == "admin_main")
async def back_to_main(callback: CallbackQuery):
    """Returns to the main dashboard."""
    text = await get_stats_text()
    await callback.message.edit_text(text, parse_mode="Markdown", reply_markup=get_admin_main_keyboard())
    await callback.answer()

@router.callback_query(F.data.startswith("mgmt_service_"))
async def manage_single_service(callback: CallbackQuery):
    """Shows options for a specific service."""
    service_id = int(callback.data.split("_")[2])
    service = await db_manager.get_service_by_id(service_id)
    
    if not service:
        await callback.answer("Service not found.", show_alert=True)
        return

    text = (
        f"🛠 *Service:* {service.name}\n\n"
        f"ID: `{service.id}`\n"
        f"Status: `{'Active' if service.is_active else 'Disabled'}`\n"
        f"Group ID: `{service.group_id}`\n"
        f"Reply ID: `{service.reply_to_message_id or 'None'}`\n"
        f"Link: {service.message_link or 'None'}\n"
        f"Total Requests: `{service.total_requests}`"
    )
    await callback.message.edit_text(
        text, 
        parse_mode="Markdown", 
        reply_markup=get_service_edit_keyboard(service_id, service.is_active)
    )
    await callback.answer()

@router.callback_query(F.data.startswith("toggle_service_"))
async def toggle_service(callback: CallbackQuery):
    """Toggles the service active status."""
    service_id = int(callback.data.split("_")[2])
    service = await db_manager.get_service_by_id(service_id)
    if service:
        new_status = not service.is_active
        await db_manager.update_service(service_id, is_active=new_status)
        await manage_single_service(callback) # Refresh the view
    await callback.answer("Status updated!")

@router.callback_query(F.data == "admin_add_service")
async def start_add_service(callback: CallbackQuery, state: FSMContext):
    """Starts the service creation FSM flow."""
    await callback.message.edit_text("Enter the *Service Name*:", parse_mode="Markdown")
    await state.set_state(AdminStates.waiting_for_service_name)
    await callback.answer()

@router.message(AdminStates.waiting_for_service_name)
async def process_service_name(message: Message, state: FSMContext):
    await state.update_data(name=message.text)
    await message.answer("Enter the *Group ID* (e.g., -100123456789):", parse_mode="Markdown")
    await state.set_state(AdminStates.waiting_for_group_id)

@router.message(AdminStates.waiting_for_group_id)
async def process_group_id(message: Message, state: FSMContext):
    try:
        group_id = int(message.text)
        await state.update_data(group_id=group_id)
        await message.answer("Enter the *Fixed Message Link* (e.g., https://t.me/... or 0 for None):", parse_mode="Markdown")
        await state.set_state(AdminStates.waiting_for_reply_id)
    except ValueError:
        await message.answer("Invalid Group ID. Please enter a number.")

@router.message(AdminStates.waiting_for_reply_id)
async def process_reply_id(message: Message, state: FSMContext):
    input_text = message.text.strip()
    data = await state.get_data()
    
    reply_id = None
    message_link = None

    if input_text != "0":
        # Check if it's a numeric ID first for backward compatibility
        if input_text.isdigit():
            reply_id = int(input_text)
            logger.info(f"[ADMIN DEBUG] Manual ID detected: {reply_id}")
        else:
            reply_id = extract_message_id(input_text)
            if reply_id:
                message_link = input_text
                logger.info(
                    f"[ADMIN DEBUG] Link detected: {input_text}\n"
                    f"Extracted ID: {reply_id}"
                )
            else:
                logger.warning(f"[ADMIN DEBUG] Failed to extract ID from link: {input_text}")
                await message.answer("❌ Invalid Link format. Please provide a valid Telegram message link or 0.")
                return

    logger.info(
        f"[ADMIN DEBUG] Storing service:\n"
        f"Name: {data['name']}\n"
        f"Group: {data['group_id']}\n"
        f"Reply ID: {reply_id}\n"
        f"Link: {message_link}"
    )

    await db_manager.create_service(
        name=data['name'],
        group_id=data['group_id'],
        reply_to_message_id=reply_id,
        message_link=message_link
    )
    
    await message.answer(f"✅ Service *{data['name']}* created successfully!", parse_mode="Markdown")
    await state.clear()

@router.callback_query(F.data.startswith("delete_service_"))
async def delete_service(callback: CallbackQuery):
    """Deletes a service."""
    service_id = int(callback.data.split("_")[2])
    await db_manager.delete_service(service_id)
    await list_services(callback)
    await callback.answer("Service deleted.")

# --- Service Editing Handlers ---

@router.callback_query(F.data.startswith("rename_service_"))
async def start_rename_service(callback: CallbackQuery, state: FSMContext):
    """Starts the service renaming flow."""
    service_id = int(callback.data.split("_")[2])
    await state.update_data(edit_service_id=service_id)
    await callback.message.edit_text("Enter the *New Service Name*:", parse_mode="Markdown")
    await state.set_state(AdminStates.waiting_for_new_name)
    await callback.answer()

@router.message(AdminStates.waiting_for_new_name)
async def process_new_name(message: Message, state: FSMContext):
    """Updates the service name."""
    data = await state.get_data()
    service_id = data.get("edit_service_id")
    new_name = message.text.strip()
    
    await db_manager.update_service(service_id, name=new_name)
    logger.info(f"[SERVICE RENAMED] service_id: {service_id} new_name: {new_name}")
    
    await message.answer(f"✅ Service renamed to: *{new_name}*", parse_mode="Markdown")
    
    # Re-display service management page
    service = await db_manager.get_service_by_id(service_id)
    text = (
        f"🛠 *Service:* {service.name}\n\n"
        f"ID: `{service.id}`\n"
        f"Status: `{'Active' if service.is_active else 'Disabled'}`\n"
        f"Group ID: `{service.group_id}`\n"
        f"Reply ID: `{service.reply_to_message_id or 'None'}`\n"
        f"Link: {service.message_link or 'None'}\n"
        f"Total Requests: `{service.total_requests}`"
    )
    await message.answer(
        text, 
        parse_mode="Markdown", 
        reply_markup=get_service_edit_keyboard(service_id, service.is_active)
    )
    await state.clear()

@router.callback_query(F.data.startswith("chgroup_service_"))
async def start_change_group_id(callback: CallbackQuery, state: FSMContext):
    """Starts the group ID change flow."""
    service_id = int(callback.data.split("_")[2])
    await state.update_data(edit_service_id=service_id)
    await callback.message.edit_text("Enter the *New Group ID* (e.g., -100123456789):", parse_mode="Markdown")
    await state.set_state(AdminStates.waiting_for_new_group_id)
    await callback.answer()

@router.message(AdminStates.waiting_for_new_group_id)
async def process_new_group_id(message: Message, state: FSMContext):
    """Updates the service group ID."""
    try:
        new_group_id = int(message.text)
        data = await state.get_data()
        service_id = data.get("edit_service_id")
        
        await db_manager.update_service(service_id, group_id=new_group_id)
        logger.info(f"[SERVICE GROUP UPDATED] service_id: {service_id} new_group_id: {new_group_id}")
        
        await message.answer(f"✅ Group ID updated to: `{new_group_id}`", parse_mode="Markdown")
        
        # Re-display service management page
        service = await db_manager.get_service_by_id(service_id)
        text = (
            f"🛠 *Service:* {service.name}\n\n"
            f"ID: `{service.id}`\n"
            f"Status: `{'Active' if service.is_active else 'Disabled'}`\n"
            f"Group ID: `{service.group_id}`\n"
            f"Reply ID: `{service.reply_to_message_id or 'None'}`\n"
            f"Link: {service.message_link or 'None'}\n"
            f"Total Requests: `{service.total_requests}`"
        )
        await message.answer(
            text, 
            parse_mode="Markdown", 
            reply_markup=get_service_edit_keyboard(service_id, service.is_active)
        )
        await state.clear()
    except ValueError:
        await message.answer("❌ Invalid Group ID. Please enter a number.")

@router.callback_query(F.data.startswith("chreply_service_"))
async def start_change_reply_id(callback: CallbackQuery, state: FSMContext):
    """Starts the reply ID/link change flow."""
    service_id = int(callback.data.split("_")[2])
    await state.update_data(edit_service_id=service_id)
    await callback.message.edit_text(
        "Enter the *New Message Link* or *Message ID*:\n"
        "Accepts:\n"
        "- Telegram message link\n"
        "- Raw message ID\n"
        "- 0 (to clear)", 
        parse_mode="Markdown"
    )
    await state.set_state(AdminStates.waiting_for_new_reply_id)
    await callback.answer()

@router.message(AdminStates.waiting_for_new_reply_id)
async def process_new_reply_id(message: Message, state: FSMContext):
    """Updates the service reply ID and link."""
    input_text = message.text.strip()
    data = await state.get_data()
    service_id = data.get("edit_service_id")
    
    reply_id = None
    message_link = None

    if input_text != "0":
        if input_text.isdigit():
            reply_id = int(input_text)
        else:
            reply_id = extract_message_id(input_text)
            if reply_id:
                message_link = input_text
            else:
                await message.answer("❌ Invalid Link format. Please provide a valid Telegram message link, raw ID, or 0.")
                return

    await db_manager.update_service(
        service_id, 
        reply_to_message_id=reply_id,
        message_link=message_link
    )
    logger.info(f"[SERVICE REPLY UPDATED] service_id: {service_id} reply_id: {reply_id} link: {message_link}")
    
    await message.answer(f"✅ Reply ID updated.", parse_mode="Markdown")
    
    # Re-display service management page
    service = await db_manager.get_service_by_id(service_id)
    text = (
        f"🛠 *Service:* {service.name}\n\n"
        f"ID: `{service.id}`\n"
        f"Status: `{'Active' if service.is_active else 'Disabled'}`\n"
        f"Group ID: `{service.group_id}`\n"
        f"Reply ID: `{service.reply_to_message_id or 'None'}`\n"
        f"Link: {service.message_link or 'None'}\n"
        f"Total Requests: `{service.total_requests}`"
    )
    await message.answer(
        text, 
        parse_mode="Markdown", 
        reply_markup=get_service_edit_keyboard(service_id, service.is_active)
    )
    await state.clear()

# --- Bulk Checking ---

@router.callback_query(F.data == "admin_bulk_check")
async def start_bulk_check(callback: CallbackQuery):
    """Starts the bulk check flow by showing active services."""
    services = await db_manager.get_all_services()
    await callback.message.edit_text(
        "📦 *Bulk Check System*\n\nSelect a service to perform a bulk check:",
        parse_mode="Markdown",
        reply_markup=get_bulk_services_keyboard(list(services))
    )
    await callback.answer()

@router.callback_query(F.data.startswith("bulk_service_"))
async def prompt_bulk_numbers(callback: CallbackQuery, state: FSMContext):
    """Prompts the admin for a list of numbers or a file."""
    service_id = int(callback.data.split("_")[2])
    service = await db_manager.get_service_by_id(service_id)
    
    if not service or not service.is_active:
        await callback.answer("Service not available.", show_alert=True)
        return
        
    await state.update_data(bulk_service_id=service_id, bulk_service_name=service.name)
    await callback.message.edit_text(
        f"📦 *Bulk Check:* `{service.name.upper()}`\n\n"
        "Send me a list of mobile numbers separated by newlines, OR upload a `.txt` file containing the numbers.\n\n"
        "_Limit: Max 100 numbers per batch to avoid limits._",
        parse_mode="Markdown"
    )
    await state.set_state(AdminStates.waiting_for_bulk_numbers)
    await callback.answer()

@router.message(AdminStates.waiting_for_bulk_numbers, F.text | F.document)
async def process_bulk_input(message: Message, state: FSMContext):
    """Processes the text or file containing numbers and extra data for bulk check."""
    raw_text = ""
    
    if message.text:
        raw_text = message.text
    elif message.document:
        if not message.document.file_name.endswith('.txt'):
            await message.answer("❌ Please upload a `.txt` file.")
            return
        
        file = await message.bot.get_file(message.document.file_id)
        file_bytes = await message.bot.download_file(file.file_path)
        raw_text = file_bytes.read().decode('utf-8')
        
    # Extract numbers and extra data
    # Format: NUMBER | EXTRA_DATA
    tasks_data = []
    seen_numbers = set()
    
    for line in raw_text.split('\n'):
        line = line.strip()
        if not line:
            continue
            
        parts = line.split('|', 1)
        raw_num = parts[0].strip().replace(" ", "").replace("+", "")
        extra_data = parts[1].strip() if len(parts) > 1 else None
        
        if raw_num and validate_mobile_number(raw_num) and raw_num not in seen_numbers:
            tasks_data.append({"mobile": raw_num, "extra": extra_data})
            seen_numbers.add(raw_num)
    
    if not tasks_data:
        await message.answer("❌ No valid mobile numbers found in the input. Please check the format.")
        return
        
    data = await state.get_data()
    service_id = data.get("bulk_service_id")
    service_name = data.get("bulk_service_name")
    
    status_msg = await message.answer(
        f"📦 *INITIALIZING BULK CHECK*\n\n"
        f"Service: `{service_name}`\n"
        f"Valid Entries: `{len(tasks_data)}`\n\n"
        f"Starting 50x parallel background workers...",
        parse_mode="Markdown"
    )
    
    await state.clear()
    
    # Start the background batch processor
    asyncio.create_task(
        process_bulk_batch(
            bot=message.bot,
            admin_id=message.from_user.id,
            service_id=service_id,
            tasks_data=tasks_data,
            service_name=service_name,
            status_message_id=status_msg.message_id
        )
    )

@router.callback_query(F.data == "admin_users")
async def start_user_search(callback: CallbackQuery, state: FSMContext):
    """Prompts for a user ID to manage."""
    await callback.message.edit_text("Enter the *Telegram ID* of the user:", parse_mode="Markdown")
    await state.set_state(AdminStates.waiting_for_user_id)
    await callback.answer()

@router.message(AdminStates.waiting_for_user_id)
async def process_user_search(message: Message, state: FSMContext):
    try:
        tg_id = int(message.text)
        user = await db_manager.get_user_by_telegram_id(tg_id)
        
        if not user:
            await message.answer("User not found in database.")
            return

        text = (
            f"👤 *User:* {user.first_name}\n"
            f"ID: `{user.telegram_id}`\n"
            f"Username: @{user.username or 'None'}\n"
            f"Banned: `{'Yes' if user.is_banned else 'No'}`\n"
            f"Joined: `{user.created_at.strftime('%Y-%m-%d %H:%M')}`"
        )
        await message.answer(text, parse_mode="Markdown", reply_markup=get_user_mgmt_keyboard(tg_id, user.is_banned))
        await state.clear()
    except ValueError:
        await message.answer("Invalid ID. Please enter a numeric Telegram ID.")

@router.callback_query(F.data == "admin_broadcast")
async def start_broadcast(callback: CallbackQuery, state: FSMContext):
    """Starts the broadcast FSM flow."""
    await callback.message.edit_text(
        "📢 *Broadcast System*\n\nPlease enter the message you want to send to all users:",
        parse_mode="Markdown"
    )
    await state.set_state(AdminStates.waiting_for_broadcast_text)
    await callback.answer()

@router.message(AdminStates.waiting_for_broadcast_text)
async def process_broadcast(message: Message, state: FSMContext):
    """Processes and sends the broadcast."""
    broadcast_text = message.text
    status_msg = await message.answer("🚀 *Broadcast in progress...*", parse_mode="Markdown")
    
    stats = await send_broadcast(message.bot, broadcast_text)
    
    await status_msg.edit_text(
        "📢 *Broadcast Finished*\n\n"
        f"📊 Total Users: `{stats['total']}`\n"
        f"✅ Success: `{stats['success']}`\n"
        f"🚫 Blocked: `{stats['blocked']}`\n"
        f"❌ Failed: `{stats['failed']}`",
        parse_mode="Markdown",
        reply_markup=get_admin_main_keyboard()
    )
    await state.clear()
