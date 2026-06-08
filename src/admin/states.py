from aiogram.fsm.state import StatesGroup, State

class AdminStates(StatesGroup):
    """FSM states for admin management flows."""
    # Service Creation
    waiting_for_service_name = State()
    waiting_for_group_id = State()
    waiting_for_reply_id = State()
    
    # Service Editing
    waiting_for_new_name = State()
    waiting_for_new_group_id = State()
    waiting_for_new_reply_id = State()
    
    # User Management
    waiting_for_user_id = State()
    
    # Broadcast
    waiting_for_broadcast_text = State()
    
    # Bulk Checking
    waiting_for_bulk_numbers = State()
