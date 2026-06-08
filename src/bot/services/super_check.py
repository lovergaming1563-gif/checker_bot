import asyncio
from aiogram import Bot
from src.database.manager import db_manager
from src.core.router import route_request
from src.utils.logger import logger
from src.database.models import Service

async def process_super_check(bot: Bot, user_id: int, mobile: str, active_services: list[Service], status_message_id: int, telegram_id: int):
    """
    Background task to process a Super Check (All-in-One).
    """
    request_ids = []
    
    # 1. Create requests and start routing
    for service in active_services:
        try:
            # Check for existing duplicate first to avoid double checking
            is_duplicate = await db_manager.check_duplicate_request(service_id=service.id, mobile_number=mobile)
            if is_duplicate:
                logger.info(f"[SUPER CHECK] Skipping duplicate for {mobile} on {service.name}")
                continue

            # Create request with is_bulk=True to suppress individual notifications
            request = await db_manager.create_request(
                user_id=user_id,
                service_id=service.id,
                mobile_number=mobile,
                is_bulk=True 
            )
            request_ids.append(request.id)
            
            # Route request
            await route_request(bot, request.id)
            
            # Small delay to avoid flooding
            await asyncio.sleep(0.5)
            
        except Exception as e:
            logger.error(f"[SUPER CHECK ERROR] Failed to route {mobile} for {service.name}: {e}")

    if not request_ids:
        try:
            await bot.edit_message_text(
                chat_id=telegram_id,
                message_id=status_message_id,
                text=f"❌ *SUPER CHECK FAILED*\n\nAll services are currently busy with this number. Please wait and try again.",
                parse_mode="Markdown"
            )
        except:
            pass
        return

    # 2. Wait for all requests to finish
    max_wait_time = 300 # 5 minutes max wait
    start_time = asyncio.get_event_loop().time()
    
    while asyncio.get_event_loop().time() - start_time < max_wait_time:
        all_done = True
        for req_id in request_ids:
            req = await db_manager.get_request_by_id(req_id)
            if req and req.status in ["PENDING", "PROCESSING"]:
                all_done = False
                break
        
        if all_done:
            break
            
        await asyncio.sleep(2)

    # 3. Aggregate Results
    report_lines = []
    report_lines.append(f"✅ *SUPER CHECK COMPLETED* ✅\n")
    report_lines.append(f"❖ *𝗧𝗮𝗿𝗴𝗲𝘁:* `{mobile}`\n")
    
    for req_id in request_ids:
        req = await db_manager.get_request_by_id(req_id)
        if req:
            service = await db_manager.get_service_by_id(req.service_id)
            service_name = service.name.upper() if service else "UNKNOWN"
            
            if req.status == "COMPLETED" and req.result_text:
                # Use heuristic to find the status line
                lines = [line.strip() for line in req.result_text.split("\n") if line.strip()]
                result_preview = "Unknown Result"
                for line in lines:
                    if any(kw in line.lower() for kw in ["registered", "success", "found", "active", "not registered", "failed"]):
                        result_preview = line
                        break
                report_lines.append(f"*{service_name}:* {result_preview}")
            elif req.status == "FAILED":
                report_lines.append(f"*{service_name}:* ❌ FAILED/TIMEOUT")
            else:
                report_lines.append(f"*{service_name}:* ⚠️ TIMEOUT")

    report_lines.append(f"\n⚡️ _Powered by @OtpServiceXOfficial_")
    report_text = "\n".join(report_lines)
    
    # 4. Send report
    try:
        await bot.edit_message_text(
            chat_id=telegram_id,
            message_id=status_message_id,
            text=report_text,
            parse_mode="Markdown"
        )
    except Exception as edit_err:
        logger.warning(f"Failed to edit super check message {status_message_id}: {edit_err}")
        try:
            await bot.send_message(chat_id=telegram_id, text=report_text, parse_mode="Markdown")
        except Exception as e:
            logger.error(f"[SUPER CHECK REPORT ERROR] Failed to send report: {e}")
