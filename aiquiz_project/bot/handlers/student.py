from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import StateFilter, CommandStart
from aiogram.fsm.context import FSMContext
import logging
import re

from bot.states import StudentStates, UserStates
from bot.keyboards.menu import (
    get_student_main_menu,
    get_question_answer_keyboard,
    get_test_results_keyboard
)
from bot.utils.api_client import APIClient

logger = logging.getLogger(__name__)

router = Router()


# ============================================
# ROLE SELECTION
# ============================================

@router.message(F.text == "👩‍🎓 Student")
async def select_student_role(message: Message, state: FSMContext):
    """User selected Student role"""
    try:
        # Register/update user as student
        await APIClient.get_or_create_user(
            telegram_id=message.from_user.id,
            full_name=message.from_user.full_name,
            username=message.from_user.username,
            role="student"
        )

        await state.set_state(StudentStates.MAIN_MENU)

        await message.answer(
            "👩‍🎓 <b>Welcome, Student!</b>\n\n"
            "You can:\n"
            "• Take tests shared by teachers\n"
            "• View your results\n"
            "• See leaderboards\n\n"
            "Use the link or QR code from your teacher to start a test!",
            reply_markup=get_student_main_menu(),
            parse_mode="HTML"
        )

    except Exception as e:
        logger.error(f"Error in select_student_role: {e}")
        await message.answer("❌ Sorry, something went wrong. Please try again.")


# ============================================
# DEEP LINK HANDLING (JOIN TEST)
# ============================================

@router.message(CommandStart(deep_link=True))
async def handle_deep_link(message: Message, state: FSMContext):
    """Handle /start test_TOKEN deep link"""

    # Extract token from deep link
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.answer("❌ Invalid test link. Please use the link provided by your teacher.")
        return

    deep_link_arg = args[1]

    # Parse: test_abc123xyz
    if not deep_link_arg.startswith("test_"):
        await message.answer("❌ Invalid test link format.")
        return

    access_token = deep_link_arg.replace("test_", "")

    logger.info(f"Student {message.from_user.id} joining test with token: {access_token}")

    # Ensure user is registered
    try:
        await APIClient.get_or_create_user(
            telegram_id=message.from_user.id,
            full_name=message.from_user.full_name,
            username=message.from_user.username,
            role="student"
        )
    except Exception as e:
        logger.error(f"Error creating user: {e}")
        await message.answer("❌ Failed to register. Please try again.")
        return

    # Start attempt
    processing_msg = await message.answer("⏳ Loading test...")

    try:
        result = await APIClient.start_attempt(
            access_token=access_token,
            telegram_id=message.from_user.id
        )

        await processing_msg.delete()

        # Save attempt data to state
        await state.update_data(
            attempt_id=result['attempt_id'],
            access_token=access_token,
            total_questions=result['total_questions'],
            current_index=0,
            score=0
        )

        await state.set_state(StudentStates.TAKING_TEST)

        # Show first question
        await show_question(message, result['current_question'], 0, result['total_questions'], state)

    except Exception as e:
        logger.error(f"Error starting attempt: {e}")
        await processing_msg.delete()
        await message.answer(
            f"❌ <b>Failed to start test</b>\n\n"
            f"Error: {str(e)}\n\n"
            "Please check:\n"
            "• The link is correct\n"
            "• The test is still active\n"
            "• You haven't exceeded attempt limits",
            parse_mode="HTML"
        )


async def show_question(message: Message, question_data: dict, index: int, total: int, state: FSMContext):
    """Display a question to the student"""

    question_id = question_data['id']
    question_text = question_data['question_text']
    options = question_data['options']
    points = question_data.get('points', 1)

    # Get current score
    data = await state.get_data()
    current_score = data.get('score', 0)

    # Format question message
    text = f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
    text += f"📝 <b>Question {index + 1} of {total}</b>\n"
    text += f"📊 Score: {current_score}/{index} | ⭐ Worth: {points} point{'s' if points > 1 else ''}\n"
    text += f"━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
    text += f"<b>{question_text}</b>\n\n"

    # Add options with letters
    labels = ['A', 'B', 'C', 'D', 'E', 'F']
    for i, option in enumerate(options):
        if i < len(labels):
            text += f"{labels[i]}) {option}\n"

    text += f"\n━━━━━━━━━━━━━━━━━━━━━━━━\n"
    text += f"Select your answer:"

    # Create keyboard with letter buttons
    keyboard = get_question_answer_keyboard(options, question_id)

    await message.answer(
        text,
        reply_markup=keyboard,
        parse_mode="HTML"
    )


# ============================================
# ANSWER SUBMISSION
# ============================================

@router.callback_query(F.data.startswith("answer:"))
async def handle_answer(callback: CallbackQuery, state: FSMContext):
    """Handle student's answer submission"""

    # Parse callback data: answer:question_id:option_index
    try:
        parts = callback.data.split(":")
        question_id = int(parts[1])
        selected_option = int(parts[2])
    except (IndexError, ValueError):
        await callback.answer("❌ Invalid answer format", show_alert=True)
        return

    data = await state.get_data()
    attempt_id = data.get('attempt_id')
    current_index = data.get('current_index', 0)
    total_questions = data.get('total_questions', 0)
    current_score = data.get('score', 0)

    if not attempt_id:
        await callback.answer("❌ No active attempt found", show_alert=True)
        return

    await callback.answer("💾 Saving answer...")

    try:
        # Submit answer to backend
        result = await APIClient.submit_answer(
            attempt_id=attempt_id,
            question_id=question_id,
            selected_option=selected_option
        )

        is_correct = result['is_correct']
        points_earned = result['points_earned']

        # Update score
        new_score = current_score + points_earned
        await state.update_data(
            score=new_score,
            current_index=current_index + 1
        )

        # Get question data from original message
        original_text = callback.message.text

        # Parse options from original message
        lines = original_text.split('\n')
        options = []
        for line in lines:
            if re.match(r'^[A-F]\)', line):
                options.append(line[3:].strip())  # Remove "A) " prefix

        # Find selected option letter
        labels = ['A', 'B', 'C', 'D', 'E', 'F']
        selected_letter = labels[selected_option] if selected_option < len(labels) else '?'

        # Build feedback message by editing original
        feedback_text = original_text.split("━━━━━━━━━━━━━━━━━━━━━━━━\nSelect your answer:")[0]

        # Mark the selected answer and correct answer
        lines = feedback_text.split('\n')
        updated_lines = []

        for line in lines:
            # Check if this line is an option
            for i, label in enumerate(labels[:len(options)]):
                if line.startswith(f"{label})"):
                    if i == selected_option and is_correct:
                        # Selected and correct
                        line = f"{label}) {options[i]} ✅"
                    elif i == selected_option and not is_correct:
                        # Selected but wrong
                        line = f"{label}) {options[i]} ❌ <i>(Your answer)</i>"
                    elif not is_correct and i == result.get('correct_option', -1):
                        # Show correct answer if wrong
                        line = f"{label}) {options[i]} ✅ <i>(Correct)</i>"
                    break
            updated_lines.append(line)

        feedback_text = '\n'.join(updated_lines)

        # Add feedback
        feedback_text += "\n━━━━━━━━━━━━━━━━━━━━━━━━\n"
        if is_correct:
            feedback_text += f"✅ <b>Correct!</b> +{points_earned} point{'s' if points_earned > 1 else ''}\n"
        else:
            feedback_text += f"❌ <b>Wrong!</b> The correct answer was {labels[result.get('correct_option', 0)]}\n"

        feedback_text += f"\n📊 <b>Score: {new_score}/{current_index + 1}</b>"

        # Remove buttons from answered question
        await callback.message.edit_text(
            feedback_text,
            parse_mode="HTML"
        )

        # Check if test is completed
        if result.get('test_completed') or current_index + 1 >= total_questions:
            # Test finished - show final results
            await finish_test(callback.message, state)
        else:
            # Show next question
            next_question = result.get('next_question')
            if next_question:
                await show_question(
                    callback.message,
                    next_question,
                    current_index + 1,
                    total_questions,
                    state
                )
            else:
                # Fallback if next_question not provided
                await finish_test(callback.message, state)

    except Exception as e:
        logger.error(f"Error handling answer: {e}")
        await callback.message.answer(
            f"❌ <b>Error submitting answer:</b>\n{str(e)}",
            parse_mode="HTML"
        )


# ============================================
# TEST COMPLETION
# ============================================

async def finish_test(message: Message, state: FSMContext):
    """Finish test and show results"""

    data = await state.get_data()
    attempt_id = data.get('attempt_id')

    if not attempt_id:
        await message.answer("❌ No active attempt found")
        return

    processing_msg = await message.answer("⏳ Calculating final results...")

    try:
        # Finalize attempt
        result = await APIClient.finish_attempt(attempt_id)

        await processing_msg.delete()

        # Format results message
        score = result['score']
        total = result['total']
        percentage = result['percentage']
        rank = result['rank']
        total_students = result['total_students']

        results_text = "━━━━━━━━━━━━━━━━━━━━━━━━\n"
        results_text += "🎉 <b>Test Completed!</b>\n"
        results_text += "━━━━━━━━━━━━━━━━━━━━━━━━\n\n"

        results_text += f"📊 <b>Your Results:</b>\n\n"
        results_text += f"✅ Score: <b>{score}/{total}</b> ({percentage}%)\n"
        results_text += f"🏆 Rank: <b>#{rank}</b> out of {total_students} students\n\n"

        # Performance message
        if percentage >= 90:
            results_text += "🌟 <b>Excellent!</b> Outstanding performance!\n"
        elif percentage >= 75:
            results_text += "👏 <b>Great job!</b> Well done!\n"
        elif percentage >= 60:
            results_text += "👍 <b>Good effort!</b> Keep practicing!\n"
        else:
            results_text += "💪 <b>Keep trying!</b> Review and try again!\n"

        results_text += "\n━━━━━━━━━━━━━━━━━━━━━━━━\n"
        results_text += "📜 Scroll up to review your answers"

        await message.answer(
            results_text,
            reply_markup=get_test_results_keyboard(attempt_id),
            parse_mode="HTML"
        )

        await state.set_state(StudentStates.VIEWING_RESULTS)

    except Exception as e:
        logger.error(f"Error finishing test: {e}")
        await processing_msg.delete()
        await message.answer(
            f"❌ <b>Error calculating results:</b>\n{str(e)}",
            parse_mode="HTML"
        )


# ============================================
# REVIEW ANSWERS
# ============================================

@router.callback_query(F.data.startswith("review:"))
async def review_answers(callback: CallbackQuery):
    """Show detailed review of all answers"""

    attempt_id = int(callback.data.split(":")[1])

    await callback.answer("📄 Loading review...")

    try:
        review_data = await APIClient.review_attempt(attempt_id)

        review_text = "━━━━━━━━━━━━━━━━━━━━━━━━\n"
        review_text += "📋 <b>Detailed Review</b>\n"
        review_text += "━━━━━━━━━━━━━━━━━━━━━━━━\n\n"

        for i, item in enumerate(review_data['review'], 1):
            status = "✅" if item['is_correct'] else "❌"
            review_text += f"{status} <b>Q{i}:</b> {item['question']}\n"

            labels = ['A', 'B', 'C', 'D', 'E', 'F']
            options = item['options']

            for j, option in enumerate(options):
                marker = ""
                if j == item['your_answer']:
                    marker = " ← Your answer"
                if j == item['correct_answer']:
                    marker += " ✅ Correct"

                review_text += f"   {labels[j]}) {option}{marker}\n"

            review_text += f"   Points: {item.get('points_earned', 0)}/{item.get('max_points', 1)}\n\n"

        await callback.message.answer(review_text, parse_mode="HTML")

    except Exception as e:
        logger.error(f"Error reviewing answers: {e}")
        await callback.answer(f"❌ Error: {str(e)}", show_alert=True)


# ============================================
# LEADERBOARD
# ============================================

@router.callback_query(F.data.startswith("leaderboard:"))
async def show_leaderboard(callback: CallbackQuery, state: FSMContext):
    """Show test leaderboard"""

    data = await state.get_data()
    access_token = data.get('access_token')

    if not access_token:
        await callback.answer("❌ Test information not found", show_alert=True)
        return

    await callback.answer("📊 Loading leaderboard...")

    try:
        leaderboard_data = await APIClient.get_leaderboard(access_token)

        leaderboard_text = "━━━━━━━━━━━━━━━━━━━━━━━━\n"
        leaderboard_text += "🏆 <b>Leaderboard</b>\n"
        leaderboard_text += "━━━━━━━━━━━━━━━━━━━━━━━━\n\n"

        for entry in leaderboard_data['leaderboard'][:10]:  # Top 10
            rank = entry['rank']
            name = entry['student_name']
            score = entry['auto_score']
            percentage = entry['percentage']

            # Medal for top 3
            if rank == 1:
                medal = "🥇"
            elif rank == 2:
                medal = "🥈"
            elif rank == 3:
                medal = "🥉"
            else:
                medal = f"{rank}."

            leaderboard_text += f"{medal} <b>{name}</b>\n"
            leaderboard_text += f"   Score: {score} ({percentage}%)\n\n"

        await callback.message.answer(leaderboard_text, parse_mode="HTML")

    except Exception as e:
        logger.error(f"Error showing leaderboard: {e}")
        await callback.answer(f"❌ Error: {str(e)}", show_alert=True)


# ============================================
# MAIN MENU ACTIONS
# ============================================

@router.callback_query(F.data == "main_menu")
async def back_to_main_menu(callback: CallbackQuery, state: FSMContext):
    """Return to main menu"""
    await callback.answer()
    await state.set_state(StudentStates.MAIN_MENU)

    await callback.message.answer(
        "🏠 <b>Main Menu</b>",
        reply_markup=get_student_main_menu(),
        parse_mode="HTML"
    )


@router.message(StateFilter(StudentStates.MAIN_MENU), F.text == "📊 My Results")
async def view_my_results(message: Message):
    """View student's results"""
    await message.answer(
        "📊 <b>My Results</b>\n\n"
        "This feature is coming soon!\n\n"
        "You'll be able to see all your test attempts and scores.",
        parse_mode="HTML"
    )


@router.message(StateFilter(StudentStates.MAIN_MENU), F.text == "🏆 Leaderboard")
async def view_leaderboard_menu(message: Message):
    """View leaderboard from menu"""
    await message.answer(
        "🏆 <b>Leaderboard</b>\n\n"
        "Take a test to see leaderboards!\n\n"
        "Ask your teacher for a test link.",
        parse_mode="HTML"
    )