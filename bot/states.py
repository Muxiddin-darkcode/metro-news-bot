from aiogram.fsm.state import State, StatesGroup

class AdminStates(StatesGroup):
    """Admin interaktiv harakatlari holatlari (FSM)."""
    waiting_for_tg_username = State()
    waiting_for_web_name = State()
    waiting_for_web_url = State()
    waiting_for_web_feed = State()
    waiting_for_test_text = State()
    waiting_for_test_source = State()
    waiting_for_new_keyword = State()
    waiting_for_remove_keyword = State()
