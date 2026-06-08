from aiogram import Bot
import asyncio
from src.database.manager import db_manager
from src.utils.logger import logger
from src.pyrogram_client.client import get_pyrogram_client
from src.core.worker import track_result

async def route_request(bot: Bot, request_id: int):
    """
    Routes a user request to the configured Telegram service group.
    """
    request = await db_manager.get_request_by_id(request_id)
    if not request:
        logger.error(f"Routing failed: Request {request_id} not found.")
        return

    service = await db_manager.get_service_by_id(request.service_id)
    if not service:
        logger.error(f"Routing failed: Service {request.service_id} not found.")
        await db_manager.update_request_status(request_id, "FAILED")
        return

    try:
        # Prepare the message content
        message_text = f"{request.mobile_number}"
        
        pyro_client = get_pyrogram_client()
        if not pyro_client:
            logger.error("Pyrogram client not initialized. Cannot route request.")
            await db_manager.update_request_status(request_id, "FAILED")
            return

        logger.info(f"[ROUTER] Sending message to {service.group_id}...")
        # Send message to the group using Pyrogram
        try:
            sent_message = await pyro_client.send_message(
                chat_id=service.group_id,
                text=message_text,
                reply_to_message_id=service.reply_to_message_id
            )
            logger.info(f"[ROUTER] Message sent! ID: {sent_message.id}")
        except Exception as reply_error:
            # If reply fails, retry without it
            logger.warning(f"Pyrogram reply failed for service {service.id}: {reply_error}. Retrying without reply.")
            sent_message = await pyro_client.send_message(
                chat_id=service.group_id,
                text=message_text
            )
            logger.info(f"[ROUTER] Message sent (no reply)! ID: {sent_message.id}")
        
        # Store group message ID and update status to PROCESSING
        # Note: Pyrogram message object uses .id instead of .message_id
        await db_manager.store_group_message_id(request_id, sent_message.id)
        await db_manager.update_request_status(request_id, "PROCESSING")
        
        # Start background worker to track result
        asyncio.create_task(track_result(bot, request_id, service.group_id, sent_message.id))
        
        logger.info(
            f"[PYROGRAM ROUTER]\n"
            f"Request ID: {request_id}\n"
            f"Service ID: {service.id}\n"
            f"Group ID: {service.group_id}\n"
            f"Reply To: {service.reply_to_message_id}\n"
            f"Sent Message ID: {sent_message.id}\n"
            f"Worker Started: Yes"
        )
        
    except Exception as e:
        logger.error(f"Critical error routing request {request_id} to group {service.group_id}: {e}")
        await db_manager.update_request_status(request_id, "FAILED")

        # Optional: Notify user about failure if needed
