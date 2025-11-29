from aiogram.fsm.state import State, StatesGroup


class UserStates(StatesGroup):
    """Common user states"""
    SELECTING_ROLE = State()  # Choosing Teacher or Student


class TeacherStates(StatesGroup):
    """Teacher conversation states"""
    MAIN_MENU = State()  # Teacher main menu

    # Test creation flow
    WAITING_TEST_INPUT = State()  # Waiting for initial test description
    CONFIRMING_TEST = State()  # Showing confirmation, can edit
    GENERATING = State()  # Calling API to generate test
    PREVIEW = State()  # Showing generated test preview

    # Test management
    VIEWING_TESTS = State()  # Viewing list of created tests
    VIEWING_RESULTS = State()  # Viewing test results/leaderboard


class StudentStates(StatesGroup):
    """Student conversation states"""
    MAIN_MENU = State()  # Student main menu

    # Test taking flow
    TAKING_TEST = State()  # Currently answering questions
    VIEWING_RESULTS = State()  # Viewing test results
    REVIEWING_ANSWERS = State()  # Reviewing correct/wrong answers