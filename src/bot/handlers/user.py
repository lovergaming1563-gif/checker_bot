from aiogram import Router, F
from aiogram.filters import CommandStart
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

from src.database.manager import db_manager
from src.database.models import User as DBUser
from src.bot.keyboards.user_keyboards import get_services_keyboard, get_cancel_keyboard
from src.bot.states import RequestStates
from src.utils.validators import validate_mobile_number
from src.utils.logger import logger
from src.core.router import route_request

router = Router(name="user_router")

@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext, db_user: DBUser):
    """Handles the /start command."""
    await state.clear()
    
    active_services = await db_manager.get_active_services()
    
    if not active_services:
        await message.answer(
            "⚡️ *Welcome to Service Checker*\n\n"
            "⚠️ Currently, there are no active services available. Please check back later.",
            parse_mode="Markdown"
        )
        return

    welcome_text = (
        f"⚡️ *𝐖𝐄𝐋𝐂𝐎𝐌𝐄, {db_user.first_name.upper()}!* ⚡️\n\n"
        f"🛡 _High-speed Telegram Checker_\n"
        f"━━━━━━━━━━━━━━━\n"
        f"🎯 *SELECT A SERVICE BELOW:*"
    )

    await message.answer(
        welcome_text,
        reply_markup=get_services_keyboard(list(active_services)),
        parse_mode="Markdown"
    )
    await state.set_state(RequestStates.selecting_service)

@router.callback_query(F.data == "check_join")
async def process_check_join(callback: CallbackQuery, state: FSMContext, db_user: DBUser):
    """Verifies membership and shows main menu if joined."""
    # The middleware will automatically handle the check.
    # If we reach here, it means membership was verified.
    await callback.answer("✅ Verified! Welcome back.", show_alert=True)
    
    # Show main menu
    active_services = await db_manager.get_active_services()
    welcome_text = (
        f"⚡️ *𝐖𝐄𝐋𝐂𝐎𝐌𝐄, {db_user.first_name.upper()}!* ⚡️\n\n"
        f"🛡 _High-speed Telegram Checker_\n"
        f"━━━━━━━━━━━━━━━\n"
        f"🎯 *SELECT A SERVICE BELOW:*"
    )
    await callback.message.edit_text(
        welcome_text,
        reply_markup=get_services_keyboard(list(active_services)),
        parse_mode="Markdown"
    )
    await state.set_state(RequestStates.selecting_service)

@router.callback_query(F.data == "cancel_request")
async def process_cancel(callback: CallbackQuery, state: FSMContext):
    """Resets the state and returns to main menu."""
    await state.clear()
    active_services = await db_manager.get_active_services()
    
    await callback.message.edit_text(
        "⚡️ *SELECT A SERVICE BELOW:*",
        reply_markup=get_services_keyboard(list(active_services)),
        parse_mode="Markdown"
    )
    await callback.answer("Request cancelled.")

@router.callback_query(F.data == "super_check", RequestStates.selecting_service)
async def process_super_check_selection(callback: CallbackQuery, state: FSMContext):
    """Handles the Super Check selection."""
    active_services = await db_manager.get_active_services()
    if not active_services:
        await callback.answer("⚠️ No active services available.", show_alert=True)
        return

    await state.update_data(is_super_check=True)
    
    prompt_text = (
        f"🌐 *𝐒𝐔𝐏𝐄𝐑 𝐂𝐇𝐄𝐂𝐊 (𝐀𝐋𝐋)*\n\n"
        f"📱 *Enter the Mobile Number below:*\n"
        f"_(Format: exactly 10 digits)_\n\n"
        f"_This will check the number across all `{len(active_services)}` active services._"
    )
    
    await callback.message.edit_text(
        prompt_text,
        reply_markup=get_cancel_keyboard(),
        parse_mode="Markdown"
    )
    await state.set_state(RequestStates.entering_mobile)
    await callback.answer()

@router.callback_query(F.data.startswith("service_"), RequestStates.selecting_service)
async def process_service_selection(callback: CallbackQuery, state: FSMContext):
    """Handles service selection from the inline keyboard."""
    service_id = int(callback.data.split("_")[1])
    service = await db_manager.get_service_by_id(service_id)
    
    if not service or not service.is_active:
        await callback.answer("⚠️ This service is no longer available.", show_alert=True)
        return

    await state.update_data(selected_service_id=service_id, service_name=service.name, is_super_check=False)
    
    prompt_text = (
        f"🎯 *𝐒𝐞𝐥𝐞𝐜𝐭𝐞𝐝:* `{service.name.upper()}`\n\n"
        f"📱 *Enter the Mobile Number below:*\n"
        f"_(Format: exactly 10 digits)_"
    )
    
    await callback.message.edit_text(
        prompt_text,
        reply_markup=get_cancel_keyboard(),
        parse_mode="Markdown"
    )
    await state.set_state(RequestStates.entering_mobile)
    await callback.answer()

@router.message(RequestStates.entering_mobile)
async def process_mobile_input(message: Message, state: FSMContext, db_user: DBUser):
    """Handles mobile number input, validates it, and creates a request."""
    mobile = message.text.strip()
    
    if not validate_mobile_number(mobile):
        await message.answer(
            "❌ *INVALID FORMAT*\n\n"
            "Please enter a valid mobile number (exactly 10 digits):",
            reply_markup=get_cancel_keyboard(),
            parse_mode="Markdown"
        )
        return

    user_data = await state.get_data()
    is_super_check = user_data.get("is_super_check", False)

    if is_super_check:
        active_services = await db_manager.get_active_services()
        if not active_services:
            await message.answer("⚠️ No active services available.")
            return
            
        receipt_text = (
            f"⏳ *SUPER CHECK INITIATED...*\n\n"
            f"❖ *Target:* `{mobile}`\n"
            f"❖ *Services:* `{len(active_services)}` Active Services\n\n"
            f"📡 _Connecting to gateways... Please wait._"
        )
        
        sent_msg = await message.answer(receipt_text, parse_mode="Markdown")
        await state.clear()
        
        # Start background super check task
        from src.bot.services.super_check import process_super_check
        import asyncio
        asyncio.create_task(
            process_super_check(
                bot=message.bot,
                user_id=db_user.id,
                mobile=mobile,
                active_services=list(active_services),
                status_message_id=sent_msg.message_id,
                telegram_id=db_user.telegram_id
            )
        )
        return

    # --- Normal Single Service Check Flow ---
    service_id = user_data.get("selected_service_id")
    service_name = user_data.get("service_name")

    # Check for duplicate pending/processing request system-wide
    is_duplicate = await db_manager.check_duplicate_request(
        service_id=service_id,
        mobile_number=mobile
    )

    if is_duplicate:
        await message.answer(
            "⚠️ *ACTIVE REQUEST EXISTS*\n\n"
            "This number is already being processed. Please wait for the current check to finish.",
            parse_mode="Markdown"
        )
        return

    # Create request
    try:
        request = await db_manager.create_request(
            user_id=db_user.id,
            service_id=service_id,
            mobile_number=mobile
        )
        
        # Plain Markdown for reliability
        receipt_text = (
            f"⏳ *REQUEST INITIATED...*\n\n"
            f"❖ *Service:* `{service_name.upper()}`\n"
            f"❖ *Target:* `{mobile}`\n"
            f"❖ *Status:* 🟡 `PENDING`\n\n"
            f"📡 _Connecting to gateway... Please wait._"
        )
        
        sent_msg = await message.answer(
            receipt_text,
            parse_mode="Markdown"
        )
        
        # Store the message ID for later editing
        await db_manager.store_user_message_id(request.id, sent_msg.message_id)
        
        await state.clear()
        
        # Trigger Routing to Group
        logger.info(f"[USER HANDLER] Calling router for request {request.id}")
        await route_request(message.bot, request.id)
        
    except Exception as e:
        logger.error(f"Error creating request: {e}")
        await message.answer("❌ *SYSTEM ERROR*\n\nPlease try again later.")
