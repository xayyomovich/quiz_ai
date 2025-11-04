from aiogram import Router, F
from aiogram.types import Message
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
import logging

from bot.states import UserStates, StudentStates
from bot.keyboards.menu import get_role_selection_keyboard
from bot.utils.api_client import APIClient

logger = logging.getLogger(__name__)

router = Router()


@router.message(CommandStart(deep_link=True))
async def handle_deep_link_start(message: Message, state: FSMContext):
    """
    Handle /start with deep link parameter
    Priority: This runs BEFORE regular /start

    Examples:
    - /start test_abc123 → Start test
    - /start teacher_invite → Teacher invite (future)
    """

    # Extract parameter
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        # No parameter, fallback to regular start
        await regular_start(message, state)
        return

    deep_link_arg = args[1]
    logger.info(f"Deep link detected: {deep_link_arg} from user {message.from_user.id}")

    # Check if it's a test link
    if deep_link_arg.startswith("test_"):
        await handle_test_link(message, state, deep_link_arg)
        return

    # Add more deep link types here in future
    # elif deep_link_arg.startswith("teacher_"):
    #     await handle_teacher_invite(message, state, deep_link_arg)

    # Unknown parameter, show regular start
    await regular_start(message, state)


async def handle_test_link(message: Message, state: FSMContext, deep_link_arg: str):
    """
    Handle test link: /start test_abc123
    Auto-register as student and start test immediately
    """

    access_token = deep_link_arg.replace("test_", "")

    logger.info(f"Test link: token={access_token}, user={message.from_user.id}")

    # Auto-register user as STUDENT
    try:
        await APIClient.get_or_create_user(
            telegram_id=message.from_user.id,
            full_name=message.from_user.full_name,
            username=message.from_user.username,
            role="student"  # Auto-register as student!
        )
        logger.info(f"User {message.from_user.id} registered as student")
    except Exception as e:
        logger.error(f"Error registering user: {e}")
        await message.answer(
            "❌ <b>Registration Failed</b>\n\n"
            "Could not register you. Please try again later.",
            parse_mode="HTML"
        )
        return

    # Show loading message
    loading_msg = await message.answer(
        "⏳ <b>Loading test...</b>\n\n"
        "Please wait a moment...",
        parse_mode="HTML"
    )

    # Start test attempt
    try:
        result = await APIClient.start_attempt(
            access_token=access_token,
            telegram_id=message.from_user.id
        )

        await loading_msg.delete()

        # Save attempt data to state
        await state.update_data(
            attempt_id=result['attempt_id'],
            access_token=access_token,
            total_questions=result['total_questions'],
            current_index=0,
            score=0
        )

        await state.set_state(StudentStates.TAKING_TEST)

        # Import here to avoid circular import
        from bot.handlers.student import show_question

        # Show first question
        try:
            logger.info(f"Showing first question for attempt {result['attempt_id']}")
            await show_question(
                message,
                result['current_question'],
                0,
                result['total_questions'],
                state
            )
            logger.info("First question displayed successfully")
        except Exception as question_error:
            logger.error(f"Error displaying question: {question_error}")
            await message.answer(
                f"❌ <b>Error displaying question</b>\n\n"
                f"Error: {str(question_error)}\n\n"
                "Please try again.",
                parse_mode="HTML"
            )
            return

        logger.info(f"Test started: attempt_id={result['attempt_id']}")

    except Exception as e:
        logger.error(f"Error starting test: {e}")
        await loading_msg.delete()

        # Show friendly error message
        error_text = "❌ <b>Could not start test</b>\n\n"

        if "404" in str(e) or "not found" in str(e).lower():
            error_text += "This test link is invalid or has been removed.\n\n"
            error_text += "Please check:\n"
            error_text += "• The link is correct\n"
            error_text += "• The test is still active\n"
            error_text += "• Ask your teacher for a new link"
        elif "exceeded" in str(e).lower() or "attempts" in str(e).lower():
            error_text += "You have reached the maximum number of attempts for this test.\n\n"
            error_text += "Contact your teacher if you need to retry."
        elif "not allowed" in str(e).lower():
            error_text += "Retakes are not allowed for this test.\n\n"
            error_text += "You have already completed this test."
        else:
            error_text += f"Error: {str(e)}\n\n"
            error_text += "Please try again or contact your teacher."

        await message.answer(error_text, parse_mode="HTML")


@router.message(Command("start"))
async def regular_start(message: Message, state: FSMContext):
    """
    Handle regular /start without deep link
    Shows role selection
    """

    logger.info(f"Regular start from user {message.from_user.id}")

    await state.set_state(UserStates.SELECTING_ROLE)

    await message.answer(
        "👋 <b>Salom! Welcome to AI QuizBot!</b>\n\n"
        "I can help you:\n\n"
        "👨‍🏫 <b>Teachers:</b> Create AI-generated tests in seconds\n"
        "👩‍🎓 <b>Students:</b> Take tests and see your results\n\n"
        "Please select your role:",
        reply_markup=get_role_selection_keyboard(),
        parse_mode="HTML"
    )