import asyncio
from aiogram import Bot
from src.database.manager import db_manager
from src.utils.logger import logger
from src.pyrogram_client.client import get_pyrogram_client
from datetime import datetime

async def track_result(bot: Bot, request_id: int, chat_id: int, message_id: int):
    """
    Background worker that polls a Telegram message for updates.
    """
    logger.info(f"[WORKER START] Tracking request {request_id} (Msg: {message_id} in {chat_id})")
    
    pyro_client = get_pyrogram_client()
    if not pyro_client:
        logger.error(f"[WORKER ERROR] Pyrogram client not available for request {request_id}")
        await db_manager.update_request_status(request_id, "FAILED")
        return

    # Fetch initial request data to know what we sent
    request = await db_manager.get_request_by_id(request_id)
    if not request:
        logger.error(f"[WORKER ERROR] Request {request_id} not found in database")
        return

    start_time = asyncio.get_event_loop().time()
    
    # Increase timeout for bulk requests because they might sit in a queue in the group
    timeout = 300 if request.is_bulk else 60
    
    waiting_keywords = ["⏳", "processing", "checking", "loading"]
    initial_text = request.mobile_number.strip().lower()
    
    try:
        while asyncio.get_event_loop().time() - start_time < timeout:
            await asyncio.sleep(1)
            
            # 0. Check if request was already completed by group_handler
            current_request = await db_manager.get_request_by_id(request_id)
            if not current_request or current_request.status == "COMPLETED":
                logger.info(f"[WORKER STOP] Request {request_id} already completed or removed.")
                return

            try:
                # 1. Fetch the original message to check for edits
                msg = await pyro_client.get_messages(chat_id, message_id)
                
                # We prioritize the message itself (edits) but also check recent history for replies
                messages_to_check = []
                if msg:
                    messages_to_check.append(msg)
                
                # 2. Fetch recent messages to find replies from other bots
                async for history_msg in pyro_client.get_chat_history(chat_id, limit=10):
                    # Skip if it's the message we already have
                    if msg and history_msg.id == msg.id:
                        continue
                    messages_to_check.append(history_msg)

                for check_msg in messages_to_check:
                    current_text = check_msg.text or check_msg.caption or ""
                    if not current_text:
                        continue

                    text_lower = current_text.lower().strip()
                    
                    # Criteria for matching:
                    # A. It's the original message (msg.id == message_id) and its text has changed
                    # B. It's a reply to our original message
                    # C. It contains the mobile number (fallback)
                    
                    is_original = (check_msg.id == message_id)
                    is_reply = (check_msg.reply_to_message and check_msg.reply_to_message.id == message_id)
                    has_number = (request.mobile_number in current_text)

                    if not (is_original or is_reply or has_number):
                        continue

                    # Skip if it's just the initial request or waiting placeholders
                    if is_original and text_lower == initial_text:
                        continue
                    
                    is_waiting = any(keyword in text_lower for keyword in waiting_keywords)
                    if is_waiting:
                        continue

                    # If we reach here, we found a potential result
                    logger.info(f"[WORKER RESULT FOUND] Request {request_id} via Msg ID: {check_msg.id}")
                    
                    # Mark as completed in DB
                    await db_manager.complete_request(request_id, current_text)
                    
                    # Skip individual notification for bulk requests
                    if current_request.is_bulk:
                        return # Exit worker successfully
                    
                    # Fetch fresh request, service and user data for notification
                    fresh_request = await db_manager.get_request_by_id(request_id)
                    service = await db_manager.get_service_by_id(request.service_id)
                    user = await db_manager.get_user_by_id(request.user_id)
                    
                    if user and service and fresh_request:
                        # Clean result text: try to find lines with common status keywords
                        lines = [line.strip() for line in current_text.split("\n") if line.strip()]
                        result_preview = current_text # default
                        
                        # Heuristic: Find the line that looks like a status
                        for line in lines:
                            if any(kw in line.lower() for kw in ["registered", "success", "found", "active", "not registered", "failed"]):
                                result_preview = line
                                break

                        result_msg = (
                            f"✅ *𝗖𝗛𝗘𝗖𝗞 𝗖𝗢𝗠𝗣𝗟𝗘𝗧𝗘𝗗* ✅\n\n"
                            f"❖ *𝗧𝗮𝗿𝗴𝗲𝘁:* `{request.mobile_number}`\n"
                            f"❖ *𝗦𝗲𝗿𝘃𝗶𝗰𝗲:* `{service.name.upper()}`\n"
                            f"❖ *𝗥𝗲𝘀𝘂𝗹𝘁:* {result_preview}\n\n"
                            f"⚡️ _Powered by @OtpServiceXOfficial_"
                        )
                        
                        # [DEBUG] Check user_message_id
                        logger.info(f"[DEBUG DELIVERY] Request: {request_id} User Msg ID: {fresh_request.user_message_id}")
                        
                        try:
                            # Attempt to edit the original status message if user_message_id exists
                            if fresh_request.user_message_id:
                                logger.info(f"[DEBUG EDIT] Attempting edit for msg {fresh_request.user_message_id}")
                                try:
                                    await bot.edit_message_text(
                                        chat_id=user.telegram_id,
                                        message_id=fresh_request.user_message_id,
                                        text=result_msg,
                                        parse_mode="Markdown"
                                    )
                                    logger.info(f"[DEBUG EDIT SUCCESS] Message {fresh_request.user_message_id} edited.")
                                except Exception as edit_err:
                                    logger.warning(f"[DEBUG EDIT FAILED] {edit_err}")
                                    # Fallback: send new message
                                    await bot.send_message(
                                        chat_id=user.telegram_id,
                                        text=result_msg,
                                        parse_mode="Markdown"
                                    )
                            else:
                                logger.info("[DEBUG SEND] No user_message_id found, sending new message.")
                                await bot.send_message(
                                    chat_id=user.telegram_id,
                                    text=result_msg,
                                    parse_mode="Markdown"
                                )
                        except Exception as send_err:
                            logger.error(f"Failed to deliver result to user {user.telegram_id}: {send_err}")
                    
                    return # Exit worker successfully

            except Exception as e:
                logger.error(f"[WORKER POLLING ERROR] Request {request_id}: {e}")
                await asyncio.sleep(1)

        # 4. Final check: if loop finishes, verify it wasn't completed in the last second
        final_request = await db_manager.get_request_by_id(request_id)
        if final_request and final_request.status == "COMPLETED":
            return

        # If loop finishes, it timed out
        logger.warning(f"[WORKER TIMEOUT] Request {request_id} timed out after {timeout}s")
        await db_manager.update_request_status(request_id, "FAILED")
        
        # Notify user about timeout
        user = await db_manager.get_user_by_id(request.user_id)
        if user:
            try:
                timeout_msg = (
                    f"❌ *𝐑𝐄𝐤𝐔𝐄𝐒𝐓 𝐓𝐈𝐌𝐄𝐃 𝐎𝐔𝐓*\n\n"
                    f"❖ *Target:* `{request.mobile_number}`\n"
                    f"⚠️ The service did not respond within {timeout} seconds. Please try again later."
                )
                await bot.send_message(
                    chat_id=user.telegram_id,
                    text=timeout_msg,
                    parse_mode="Markdown"
                )
            except Exception as e:
                logger.error(f"Failed to send timeout notification to user {user.telegram_id}: {e}")

    except Exception as e:
        logger.critical(f"[WORKER CRITICAL ERROR] Request {request_id}: {e}")
        await db_manager.update_request_status(request_id, "FAILED")

