from aiogram.fsm.state import StatesGroup, State

class RequestStates(StatesGroup):
    """FSM states for the user request flow."""
    selecting_service = State()
    entering_mobile = State()
