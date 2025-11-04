from aiogram.types import (
    ReplyKeyboardMarkup, 
    KeyboardButton,
    InlineKeyboardMarkup,
    InlineKeyboardButton
)


# ============================================
# ROLE SELECTION
# ============================================

def get_role_selection_keyboard():
    """Initial role selection keyboard"""
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="👨‍🏫 Teacher")],
            [KeyboardButton(text="👩‍🎓 Student")],
        ],
        resize_keyboard=True,
        one_time_keyboard=True
    )
    return keyboard


# ============================================
# TEACHER KEYBOARDS
# ============================================

def get_teacher_main_menu():
    """Teacher main menu keyboard"""
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="➕ Create Test")],
            [KeyboardButton(text="📋 My Tests"), KeyboardButton(text="📊 View Results")],
            [KeyboardButton(text="🏆 Leaderboard")],
        ],
        resize_keyboard=True
    )
    return keyboard


def get_confirm_test_keyboard():
    """Inline keyboard for test confirmation"""
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ Confirm and Generate", callback_data="confirm_test")],
        ]
    )
    return keyboard


def get_test_preview_keyboard(test_id):
    """Inline keyboard for test preview actions"""
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📤 Publish & Share", callback_data=f"publish_test:{test_id}")],
            [InlineKeyboardButton(text="👁️ View All Questions", callback_data=f"view_all:{test_id}")],
            [InlineKeyboardButton(text="🔄 Regenerate", callback_data=f"regenerate:{test_id}")],
            [InlineKeyboardButton(text="❌ Discard", callback_data=f"discard:{test_id}")],
        ]
    )
    return keyboard


def get_published_test_keyboard():
    """Keyboard after test is published"""
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📊 View Results", callback_data="view_results")],
            [InlineKeyboardButton(text="➕ Create Another Test", callback_data="create_new_test")],
        ]
    )
    return keyboard


# ============================================
# STUDENT KEYBOARDS
# ============================================

def get_student_main_menu():
    """Student main menu keyboard"""
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📊 My Results")],
            [KeyboardButton(text="🏆 Leaderboard")],
        ],
        resize_keyboard=True
    )
    return keyboard


def get_question_answer_keyboard(options, question_id):
    """
    Inline keyboard for answering MCQ questions
    Single row of letter buttons: [A] [B] [C] [D]
    """
    labels = ['A', 'B', 'C', 'D', 'E', 'F']
    
    # Create single row with letter buttons
    buttons = []
    for i, option in enumerate(options):
        if i < len(labels):
            buttons.append(
                InlineKeyboardButton(
                    text=labels[i],
                    callback_data=f"answer:{question_id}:{i}"
                )
            )
    
    # Single row
    keyboard = InlineKeyboardMarkup(inline_keyboard=[buttons])
    return keyboard


def get_test_results_keyboard(attempt_id):
    """Keyboard for test results actions"""
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔍 Review Answers", callback_data=f"review:{attempt_id}")],
            [InlineKeyboardButton(text="🏆 View Leaderboard", callback_data=f"leaderboard:{attempt_id}")],
            [InlineKeyboardButton(text="🏠 Main Menu", callback_data="main_menu")],
        ]
    )
    return keyboard


# ============================================
# COMMON KEYBOARDS
# ============================================

def get_back_to_menu_keyboard():
    """Simple back to main menu keyboard"""
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🏠 Main Menu")],
        ],
        resize_keyboard=True
    )
    return keyboard


def get_cancel_keyboard():
    """Cancel current action keyboard"""
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="❌ Cancel")],
        ],
        resize_keyboard=True
    )
    return keyboard