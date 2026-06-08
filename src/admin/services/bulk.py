import asyncio
from aiogram import Bot
from src.database.manager import db_manager
from src.core.router import route_request
from src.utils.logger import logger
from aiogram.types import BufferedInputFile
import io
import random

async def bulk_worker(name: str, queue: asyncio.Queue, bot: Bot, service_id: int, admin_id: int, results_list: list):
    """Consumer task that processes bulk requests from the queue."""
    while True:
        task_data = await queue.get()
        mobile = task_data['mobile']
        extra = task_data['extra']
        
        try:
            # Check for existing duplicate
            is_duplicate = await db_manager.check_duplicate_request(service_id=service_id, mobile_number=mobile)
            if is_duplicate:
                logger.info(f"[BULK WORKER {name}] Skipping duplicate {mobile}")
                queue.task_done()
                continue

            # Get user id for the admin
            admin_user = await db_manager.get_user_by_telegram_id(admin_id)
            if not admin_user:
                queue.task_done()
                continue

            # Create request with extra data
            request = await db_manager.create_request(
                user_id=admin_user.id,
                service_id=service_id,
                mobile_number=mobile,
                is_bulk=True,
                extra_data=extra
            )
            
            results_list.append(request.id)
            
            # Route request
            await route_request(bot, request.id)
            
            # Random delay between 0.5 and 2 seconds to avoid flood limits while still being fast
            await asyncio.sleep(random.uniform(0.5, 2.0))
            
        except Exception as e:
            logger.error(f"[BULK WORKER {name} ERROR] Failed to route {mobile}: {e}")
        finally:
            queue.task_done()

async def process_bulk_batch(bot: Bot, admin_id: int, service_id: int, tasks_data: list, service_name: str, status_message_id: int = None):
    """
    Background task to process a bulk check request using an asyncio queue.
    """
    total = len(tasks_data)
    request_ids = []
    
    # 1. Setup Queue and Workers
    queue = asyncio.Queue()
    for task in tasks_data:
        queue.put_nowait(task)
        
    num_workers = min(50, total) # Up to 50 parallel workers
    workers = []
    for i in range(num_workers):
        task = asyncio.create_task(bulk_worker(f"W-{i}", queue, bot, service_id, admin_id, request_ids))
        workers.append(task)
        
    # Wait for queue to be fully routed
    # We update status while waiting
    while not queue.empty():
        remaining = queue.qsize()
        if status_message_id:
            try:
                await bot.edit_message_text(
                    chat_id=admin_id,
                    message_id=status_message_id,
                    text=f"📦 *BULK CHECK ROUTING*\n\nService: `{service_name}`\nRouted: `{total - remaining}/{total}`\n\n_Using {num_workers} parallel workers..._",
                    parse_mode="Markdown"
                )
            except:
                pass
        await asyncio.sleep(2)
        
    # Wait for all routing to finish
    await queue.join()
    
    # Cancel workers
    for w in workers:
        w.cancel()

    # 2. Wait for all requests to finish checking
    if status_message_id:
        try:
            await bot.edit_message_text(
                chat_id=admin_id,
                message_id=status_message_id,
                text=f"📦 *BULK CHECK WAITING*\n\nService: `{service_name}`\nAll `{len(request_ids)}` numbers routed.\n\n_Waiting for results from the checker bot (Max 10 mins)..._",
                parse_mode="Markdown"
            )
        except:
            pass

    # Dynamic timeout based on batch size. 10 mins max.
    max_wait_time = 600 
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
            
        await asyncio.sleep(5)

    # 3. Aggregate Categorized Results
    registered = []
    not_registered = []
    errors = []
    
    for req_id in request_ids:
        req = await db_manager.get_request_by_id(req_id)
        if req:
            mobile = req.mobile_number
            extra = f" | {req.extra_data}" if req.extra_data else ""
            original_input = f"{mobile}{extra}"
            
            if req.status == "COMPLETED" and req.result_text:
                # Use heuristic to find the status line
                is_reg = False
                lines = [line.strip().lower() for line in req.result_text.split("\n") if line.strip()]
                
                # Simple heuristic: if 'not registered' or 'failed' is in any line, it's not registered
                if any(kw in " ".join(lines) for kw in ["not registered", "not found", "failed", "invalid"]):
                    not_registered.append(original_input)
                elif any(kw in " ".join(lines) for kw in ["registered", "success", "found", "active"]):
                    registered.append(original_input)
                else:
                    # Fallback if unclear
                    errors.append(f"{original_input} -> UNKNOWN RESULT")
            elif req.status == "FAILED":
                errors.append(f"{original_input} -> FAILED/TIMEOUT")
            else:
                errors.append(f"{original_input} -> TIMEOUT")

    # Build the report string
    report_lines = []
    report_lines.append(f"📦 BULK CHECK REPORT - {service_name.upper()} 📦")
    report_lines.append(f"Total Processed: {len(request_ids)}")
    report_lines.append(f"Registered: {len(registered)}")
    report_lines.append(f"Not Registered: {len(not_registered)}")
    report_lines.append(f"Errors/Timeouts: {len(errors)}")
    report_lines.append("--------------------------------------------------\n")
    
    if registered:
        report_lines.append("✅ REGISTERED:")
        report_lines.extend(registered)
        report_lines.append("")
        
    if not_registered:
        report_lines.append("❌ NOT REGISTERED:")
        report_lines.extend(not_registered)
        report_lines.append("")
        
    if errors:
        report_lines.append("⚠️ ERRORS / TIMEOUTS:")
        report_lines.extend(errors)

    report_text = "\n".join(report_lines)
    
    # 4. Send report
    try:
        # If report is too long, send as file
        if len(report_text) > 4000:
            file = BufferedInputFile(report_text.encode('utf-8'), filename=f"bulk_report_{service_name}.txt")
            await bot.send_document(
                chat_id=admin_id,
                document=file,
                caption=f"✅ *BULK CHECK FINISHED*\nService: `{service_name}`\nProcessed: `{len(request_ids)}` numbers.\n\nRegistered: `{len(registered)}`\nNot Registered: `{len(not_registered)}`",
                parse_mode="Markdown"
            )
            if status_message_id:
                await bot.delete_message(chat_id=admin_id, message_id=status_message_id)
        else:
            final_msg = f"✅ *BULK CHECK FINISHED*\n\n`{report_text}`"
            if status_message_id:
                await bot.edit_message_text(
                    chat_id=admin_id,
                    message_id=status_message_id,
                    text=final_msg,
                    parse_mode="Markdown"
                )
            else:
                await bot.send_message(chat_id=admin_id, text=final_msg, parse_mode="Markdown")
                
    except Exception as e:
        logger.error(f"[BULK REPORT ERROR] Failed to send report: {e}")
