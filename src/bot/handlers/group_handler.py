import re
from aiogram import Router, F
from aiogram.types import Message
from src.database.manager import db_manager
from src.utils.logger import logger

router = Router(name="group_router")

# Regex to find mobile numbers in messages (exactly 10 digits)
MOBILE_PATTERN = re.compile(r"(\d{10})")

@router.edited_message()
async def handle_edited_group_message(message: Message):
    """
    Dedicated handler for edited messages to ensure they are never missed.
    """
    text = message.text or message.caption
    if not text:
        return

    logger.info(
        f"[EDIT RECEIVED]\n"
        f"message_id: {message.message_id}\n"
        f"chat_id: {message.chat.id}\n"
        f"text: {text}"
    )

    # Run the same processing logic
    await process_group_message_content(message, text)

@router.message(F.chat.type.in_({"group", "supergroup"}))
async def handle_group_message(message: Message):
    """
    Listens to new messages in groups.
    """
    text = message.text or message.caption
    if not text:
        return

    reply_to = message.reply_to_message.message_id if message.reply_to_message else None
    logger.info(
        f"[NEW GROUP MESSAGE]\n"
        f"message_id: {message.message_id}\n"
        f"reply_to_message_id: {reply_to}\n"
        f"text: {text}"
    )
    
    await process_group_message_content(message, text)

async def process_group_message_content(message: Message, text: str):
    """
    Core logic to extract numbers and match requests from message content.
    """
    group_id = message.chat.id
    reply_to_id = message.reply_to_message.message_id if message.reply_to_message else None
    
    # 1. Check if this is a reply to a known request (priority detection)
    if reply_to_id:
        request = await db_manager.get_request_by_group_message_id(group_id, reply_to_id)
        if request:
            logger.info(f"[REPLY RESULT FOUND] request_id: {request.id} mobile: {request.mobile_number}")
            await complete_and_notify(message, request, text, request.mobile_number)
            return

    # 2. Extract potential mobile numbers for general detection
    matches = MOBILE_PATTERN.findall(text)
    if not matches:
        return

    # 3. Keywords to ignore (only if it's just a placeholder)
    ignore_keywords = ["⏳", "processing", "checking", "loading"]
    has_ignore_keyword = any(keyword in text.lower() for keyword in ignore_keywords)
    
    for mobile_number in matches:
        # Determine if this is a "placeholder" or a "final result"
        cleaned_text = text.strip().replace(" ", "").replace("\n", "").replace("+", "")
        clean_mobile = mobile_number.replace("+", "")
        
        # If text is exactly the number (ignoring + and whitespace), it's a placeholder
        is_just_number = cleaned_text == clean_mobile
        
        # If it's just a number OR it has an ignore keyword and very little other text, skip
        if is_just_number or (has_ignore_keyword and len(text) < len(mobile_number) + 15):
            # Find matching request to log that we are waiting
            request = await db_manager.find_matching_request(group_id, mobile_number)
            if request:
                logger.info(f"[WAITING FOR RESULT] request_id: {request.id} mobile_number: {mobile_number}")
            continue

        # 4. Valid result detected via mobile number match
        request = await db_manager.find_matching_request(group_id, mobile_number)
        if not request:
            continue

        logger.info(f"[NUMBER RESULT FOUND] request_id: {request.id} mobile_number: {mobile_number}")
        await complete_and_notify(message, request, text, mobile_number)

async def complete_and_notify(message: Message, request, text: str, mobile_number: str):
    """Helper to complete request and notify user."""
    # Complete the request in database
    await db_manager.complete_request(request.id, text)
    
    # Refetch request to get the latest data (including user_message_id and is_bulk)
    fresh_request = await db_manager.get_request_by_id(request.id)
    if not fresh_request:
        return
        
    # Skip individual notification for bulk requests
    if fresh_request.is_bulk:
        return

    # Fetch service info for the premium card
    service = await db_manager.get_service_by_id(request.service_id)
    service_name = service.name.upper() if service else "UNKNOWN"

    # Notify the original user
    db_user = await db_manager.get_user_by_id(request.user_id)
    if db_user:
        try:
            # Clean result text: try to find lines with common status keywords
            lines = [line.strip() for line in text.split("\n") if line.strip()]
            result_preview = text # default
            
            for line in lines:
                if any(kw in line.lower() for kw in ["registered", "success", "found", "active", "not registered", "failed"]):
                    result_preview = line
                    break

            result_msg = (
                f"✅ *𝗖𝗛𝗘𝗖𝗞 𝗖𝗢𝗠𝗣𝗟𝗘𝗧𝗘𝗗* ✅\n\n"
                f"❖ *𝗧𝗮𝗿𝗴𝗲𝘁:* `{mobile_number}`\n"
                f"❖ *𝗦𝗲𝗿𝘃𝗶𝗰𝗲:* `{service_name}`\n"
                f"❖ *𝗥𝗲𝘀𝘂𝗹𝘁:* {result_preview}\n\n"
                f"⚡️ _Powered by @OtpServiceXOfficial_"
            )
            
            # Attempt to edit the original status message if user_message_id exists
            if fresh_request.user_message_id:
                try:
                    await message.bot.edit_message_text(
                        chat_id=db_user.telegram_id,
                        message_id=fresh_request.user_message_id,
                        text=result_msg,
                        parse_mode="Markdown"
                    )
                except Exception as edit_err:
                    logger.warning(f"Failed to edit message {fresh_request.user_message_id} for user {db_user.telegram_id}: {edit_err}")
                    # Fallback: send new message
                    await message.bot.send_message(
                        chat_id=db_user.telegram_id,
                        text=result_msg,
                        parse_mode="Markdown"
                    )
            else:
                await message.bot.send_message(
                    chat_id=db_user.telegram_id,
                    text=result_msg,
                    parse_mode="Markdown"
                )
        except Exception as e:
            logger.error(f"Failed to deliver result to user {db_user.telegram_id} for request {request.id}: {e}")
