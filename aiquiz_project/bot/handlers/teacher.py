from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import StateFilter, Command
from aiogram.fsm.context import FSMContext
import logging

from bot.states import TeacherStates, UserStates
from bot.keyboards.menu import (
    get_teacher_main_menu,
    get_confirm_test_keyboard,
    get_test_preview_keyboard,
    get_published_test_keyboard,
    get_cancel_keyboard,
    get_role_selection_keyboard
)
from bot.utils.api_client import APIClient

logger = logging.getLogger(__name__)

router = Router()


# ============================================
# ROLE SELECTION & MAIN MENU
# ============================================

@router.message(F.text == "👨‍🏫 Teacher")
async def select_teacher_role(message: Message, state: FSMContext):
    """User selected Teacher role"""
    try:
        # Register/update user as teacher
        await APIClient.get_or_create_user(
            telegram_id=message.from_user.id,
            full_name=message.from_user.full_name,
            username=message.from_user.username,
            role="teacher"
        )

        await state.set_state(TeacherStates.MAIN_MENU)

        await message.answer(
            "👨‍🏫 <b>Welcome, Teacher!</b>\n\n"
            "I can help you create AI-generated tests in seconds.\n\n"
            "<b>What would you like to do?</b>",
            reply_markup=get_teacher_main_menu(),
            parse_mode="HTML"
        )

    except Exception as e:
        logger.error(f"Error in select_teacher_role: {e}")
        await message.answer(
            "❌ Sorry, something went wrong. Please try again."
        )


# ============================================
# TEST CREATION FLOW
# ============================================

@router.message(StateFilter(TeacherStates.MAIN_MENU), F.text == "➕ Create Test")
async def start_test_creation(message: Message, state: FSMContext):
    """Teacher wants to create a new test"""
    await state.set_state(TeacherStates.WAITING_TEST_INPUT)

    await message.answer(
        "📝 <b>Create a New Test</b>\n\n"
        "Tell me what kind of test you want to create.\n\n"
        "<b>Examples:</b>\n"
        "• <i>biology test</i>\n"
        "• <i>15 intermediate physics questions</i>\n"
        "• <i>20 hard math questions in Uzbek</i>\n"
        "• <i>математика 10 вопросов</i>\n\n"
        "Just describe what you need! 💬",
        reply_markup=get_cancel_keyboard(),
        parse_mode="HTML"
    )


@router.message(StateFilter(TeacherStates.WAITING_TEST_INPUT))
async def receive_test_input(message: Message, state: FSMContext):
    """Teacher entered initial test description"""

    if message.text == "❌ Cancel":
        await state.set_state(TeacherStates.MAIN_MENU)
        await message.answer(
            "❌ Cancelled.",
            reply_markup=get_teacher_main_menu()
        )
        return

    user_input = message.text

    # Show processing message
    processing_msg = await message.answer("⏳ Processing your request...")

    try:
        # Call confirmation API (Flash-8B parses input)
        params = await APIClient.confirm_test(
            teacher_id=message.from_user.id,
            prompt=user_input
        )

        # Save params to state
        await state.update_data(last_params=params)
        await state.set_state(TeacherStates.CONFIRMING_TEST)

        # Delete processing message
        await processing_msg.delete()

        # Show confirmation
        await message.answer(
            f"✨ <b>I will create:</b>\n\n"
            f"📝 <code>{params['description']}</code>\n\n"
            f"<b>Parameters:</b>\n"
            f"• 📚 Topic: {params['topic']}\n"
            f"• 🔢 Questions: {params['question_count']}\n"
            f"• 📊 Difficulty: {params['difficulty'].capitalize()}\n"
            f"• 🌐 Language: {params['language'].capitalize()}\n\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n"
            f"💡 <b>To modify:</b>\n\n"
            f"1️⃣ <b>Copy & edit this:</b>\n"
            f"<code>{params['description']}</code>\n\n"
            f"2️⃣ <b>Or just tell me what to change:</b>\n"
            f"• \"15 questions\"\n"
            f"• \"hard difficulty\"\n"
            f"• \"in Uzbek\" etc.",
            reply_markup=get_confirm_test_keyboard(),
            parse_mode="HTML"
        )

    except Exception as e:
        logger.error(f"Error in receive_test_input: {e}")
        await processing_msg.delete()
        await message.answer(
            f"❌ <b>Error:</b> {str(e)}\n\n"
            "Please try again with a different description.",
            parse_mode="HTML"
        )
        await state.set_state(TeacherStates.WAITING_TEST_INPUT)


@router.message(StateFilter(TeacherStates.CONFIRMING_TEST))
async def receive_modification(message: Message, state: FSMContext):
    """Teacher sent a modification while in confirmation state"""

    if message.text == "❌ Cancel":
        await state.set_state(TeacherStates.MAIN_MENU)
        await message.answer(
            "❌ Cancelled.",
            reply_markup=get_teacher_main_menu()
        )
        return

    user_input = message.text
    data = await state.get_data()
    last_params = data.get('last_params')

    # Show processing message
    processing_msg = await message.answer("⏳ Updating parameters...")

    try:
        # Call confirmation API with context (context-aware parsing)
        params = await APIClient.confirm_test(
            teacher_id=message.from_user.id,
            prompt=user_input,
            context=last_params
        )

        # Update state with new params
        await state.update_data(last_params=params)

        # Delete processing message
        await processing_msg.delete()

        # Show updated confirmation
        await message.answer(
            f"✅ <b>Updated! I will create:</b>\n\n"
            f"📝 <code>{params['description']}</code>\n\n"
            f"<b>Parameters:</b>\n"
            f"• 📚 Topic: {params['topic']}\n"
            f"• 🔢 Questions: {params['question_count']}\n"
            f"• 📊 Difficulty: {params['difficulty'].capitalize()}\n"
            f"• 🌐 Language: {params['language'].capitalize()}\n\n"
            f"💡 Still want to change? Send another message!",
            reply_markup=get_confirm_test_keyboard(),
            parse_mode="HTML"
        )

    except Exception as e:
        logger.error(f"Error in receive_modification: {e}")
        await processing_msg.delete()
        await message.answer(
            f"❌ <b>Error:</b> {str(e)}\n\n"
            "Please try again.",
            parse_mode="HTML"
        )


@router.callback_query(F.data == "confirm_test")
async def confirm_and_generate(callback: CallbackQuery, state: FSMContext):
    """Teacher clicked Confirm button"""

    data = await state.get_data()
    params = data.get('last_params')

    if not params:
        await callback.answer("❌ Error: No parameters found", show_alert=True)
        return

    await callback.answer()

    # Update message to show generating status
    await callback.message.edit_text(
        "⏳ <b>Generating your test...</b>\n\n"
        "This may take 5-10 seconds. Please wait...",
        parse_mode="HTML"
    )

    await state.set_state(TeacherStates.GENERATING)

    try:
        # Call generation API (Gemini Flash generates test)
        result = await APIClient.generate_test(
            teacher_id=callback.from_user.id,
            params=params
        )

        test_id = result['test_id']

        # Get test preview
        preview = await APIClient.get_test_preview(test_id)

        # Save test_id to state
        await state.update_data(current_test_id=test_id)
        await state.set_state(TeacherStates.PREVIEW)

        # Show preview with first 2 questions
        preview_text = f"✅ <b>Test Generated Successfully!</b>\n\n"
        preview_text += f"📝 <b>{preview['title']}</b>\n"
        preview_text += f"📄 {preview['description']}\n\n"
        preview_text += f"📊 <b>Statistics:</b>\n"
        preview_text += f"• Questions: {len(preview['questions'])}\n"
        preview_text += f"• Total Points: {sum(q['points'] for q in preview['questions'])}\n"
        preview_text += f"• Difficulty: {params['difficulty'].capitalize()}\n\n"

        # Show first 2 questions as preview
        preview_text += "📋 <b>Preview (first 2 questions):</b>\n\n"

        for i, question in enumerate(preview['questions'][:2], 1):
            preview_text += f"<b>Q{i}:</b> {question['question_text']}\n"
            for j, option in enumerate(question['options']):
                label = chr(65 + j)  # A, B, C, D
                preview_text += f"   {label}) {option}\n"
            preview_text += "\n"

        if len(preview['questions']) > 2:
            preview_text += f"<i>... and {len(preview['questions']) - 2} more questions</i>\n"

        await callback.message.edit_text(
            preview_text,
            reply_markup=get_test_preview_keyboard(test_id),
            parse_mode="HTML"
        )

    except Exception as e:
        logger.error(f"Error in confirm_and_generate: {e}")
        await callback.message.edit_text(
            f"❌ <b>Generation Failed</b>\n\n"
            f"Error: {str(e)}\n\n"
            "Please try again.",
            parse_mode="HTML"
        )
        await state.set_state(TeacherStates.MAIN_MENU)


@router.callback_query(F.data.startswith("publish_test:"))
async def publish_test(callback: CallbackQuery, state: FSMContext):
    """Teacher wants to publish the test"""

    test_id = int(callback.data.split(":")[1])

    await callback.answer("📤 Publishing test...")

    try:
        # Publish test and get shareable link
        result = await APIClient.publish_test(test_id)

        access_token = result['access_token']
        bot_link = result['bot_link']

        # Format message with link and instructions
        message_text = (
            "🎉 <b>Test Published Successfully!</b>\n\n"
            f"📝 <b>Test ID:</b> <code>{test_id}</code>\n"
            f"🔑 <b>Access Token:</b> <code>{access_token}</code>\n\n"
            f"🔗 <b>Share this link with students:</b>\n"
            f"<code>{bot_link}</code>\n\n"
            f"📱 <b>Or show them this QR code:</b>\n"
            f"(QR code coming soon...)\n\n"
            f"💡 Students can click the link or scan QR to take the test!"
        )

        await callback.message.edit_text(
            message_text,
            reply_markup=get_published_test_keyboard(),
            parse_mode="HTML"
        )

        await state.set_state(TeacherStates.MAIN_MENU)

    except Exception as e:
        logger.error(f"Error in publish_test: {e}")
        await callback.answer(f"❌ Error: {str(e)}", show_alert=True)


@router.callback_query(F.data.startswith("view_all:"))
async def view_all_questions(callback: CallbackQuery):
    """Show all questions in the test"""

    test_id = int(callback.data.split(":")[1])

    await callback.answer("📄 Loading all questions...")

    try:
        preview = await APIClient.get_test_preview(test_id)

        # Format all questions
        questions_text = f"📝 <b>{preview['title']}</b>\n\n"

        for i, question in enumerate(preview['questions'], 1):
            questions_text += f"<b>Q{i}:</b> {question['question_text']}\n"
            for j, option in enumerate(question['options']):
                label = chr(65 + j)
                # Mark correct answer
                marker = " ✅" if j == question['correct_option'] else ""
                questions_text += f"   {label}) {option}{marker}\n"
            questions_text += f"<i>Points: {question['points']}</i>\n\n"

        # Send as new message (too long for edit)
        await callback.message.answer(
            questions_text,
            parse_mode="HTML"
        )

        await callback.answer()

    except Exception as e:
        logger.error(f"Error in view_all_questions: {e}")
        await callback.answer(f"❌ Error: {str(e)}", show_alert=True)


@router.callback_query(F.data.startswith("regenerate:"))
async def regenerate_test(callback: CallbackQuery, state: FSMContext):
    """Regenerate test with same parameters"""

    await callback.answer("🔄 Regenerating test...")

    data = await state.get_data()
    params = data.get('last_params')

    if not params:
        await callback.answer("❌ Error: Parameters not found", show_alert=True)
        return

    # Go back to confirmation state
    await state.set_state(TeacherStates.CONFIRMING_TEST)

    await callback.message.edit_text(
        f"🔄 <b>Let's try again!</b>\n\n"
        f"Current parameters:\n"
        f"📝 <code>{params['description']}</code>\n\n"
        f"You can modify or confirm to regenerate.",
        reply_markup=get_confirm_test_keyboard(),
        parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("discard:"))
async def discard_test(callback: CallbackQuery, state: FSMContext):
    """Discard the generated test"""

    await callback.answer("❌ Test discarded")
    await state.set_state(TeacherStates.MAIN_MENU)

    await callback.message.edit_text(
        "❌ Test discarded.\n\n"
        "Use the menu to create a new test.",
        parse_mode="HTML"
    )


@router.callback_query(F.data == "create_new_test")
async def create_new_test_callback(callback: CallbackQuery, state: FSMContext):
    """Create another test (from callback)"""
    await callback.answer()
    await start_test_creation(callback.message, state)


# ============================================
# MY TESTS & RESULTS
# ============================================

@router.message(StateFilter(TeacherStates.MAIN_MENU), F.text == "📋 My Tests")
async def view_my_tests(message: Message, state: FSMContext):
    """View teacher's created tests with actions"""

    processing_msg = await message.answer("⏳ Loading your tests...")

    try:
        tests = await APIClient.get_teacher_tests(message.from_user.id)

        await processing_msg.delete()

        if not tests or len(tests) == 0:
            await message.answer(
                "📋 <b>My Tests</b>\n\n"
                "You haven't created any tests yet.\n\n"
                "Use <b>➕ Create Test</b> to get started!",
                parse_mode="HTML"
            )
            return

        # Create inline keyboard with test selection buttons
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

        buttons = []
        for idx, test in enumerate(tests[:15], 1):  # Show up to 15 tests
            test_title = test['title']
            test_id = test['id']
            question_count = test.get('question_count', 0)

            # Truncate title if too long
            display_title = test_title[:35] + "..." if len(test_title) > 35 else test_title

            button_text = f"{idx}. {display_title} ({question_count}Q)"
            buttons.append([
                InlineKeyboardButton(
                    text=button_text,
                    callback_data=f"select_test:{test_id}"
                )
            ])

        keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)

        await message.answer(
            "📋 <b>My Tests</b>\n\n"
            "Select a test to view content, get link, or see results:",
            reply_markup=keyboard,
            parse_mode="HTML"
        )

        await state.set_state(TeacherStates.VIEWING_TESTS)

    except Exception as e:
        logger.error(f"Error in view_my_tests: {e}")
        await processing_msg.delete()
        await message.answer(
            f"❌ <b>Error:</b> {str(e)}",
            parse_mode="HTML"
        )


@router.callback_query(F.data.startswith("select_test:"))
async def test_selected(callback: CallbackQuery, state: FSMContext):
    """Teacher selected a test - show action buttons"""

    test_id = int(callback.data.split(":")[1])

    await callback.answer()

    try:
        # Get test details
        test = await APIClient.get_test_preview(test_id)

        # Save test_id to state for later actions
        await state.update_data(selected_test_id=test_id)

        # Build info message
        text = f"📝 <b>{test['title']}</b>\n\n"
        text += f"📚 Topic: {test.get('topic', 'N/A')}\n"
        text += f"📊 Difficulty: {test.get('difficulty', 'N/A').capitalize()}\n"
        text += f"❓ Questions: {len(test['questions'])}\n"
        text += f"⭐ Total Points: {sum(q['points'] for q in test['questions'])}\n\n"
        text += "What would you like to do?"

        # Create action buttons
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📖 View Content", callback_data=f"view_content:{test_id}")],
            [InlineKeyboardButton(text="🔗 Get Share Link", callback_data=f"get_link:{test_id}")],
            [InlineKeyboardButton(text="📊 View Results", callback_data=f"view_results:{test_id}")],
            [InlineKeyboardButton(text="⬅️ Back to My Tests", callback_data="back_to_tests")]
        ])

        await callback.message.edit_text(
            text,
            reply_markup=keyboard,
            parse_mode="HTML"
        )

    except Exception as e:
        logger.error(f"Error in test_selected: {e}")
        await callback.answer(f"❌ Error: {str(e)}", show_alert=True)


@router.callback_query(F.data.startswith("view_content:"))
async def view_test_content(callback: CallbackQuery):
    """Show all questions and answers for the test"""

    test_id = int(callback.data.split(":")[1])

    await callback.answer("📖 Loading test content...")

    try:
        test = await APIClient.get_test_preview(test_id)

        # Build content message
        text = "━━━━━━━━━━━━━━━━━━━━━━━━\n"
        text += f"📝 <b>{test['title']}</b>\n"
        text += "━━━━━━━━━━━━━━━━━━━━━━━━\n\n"

        text += f"📚 <b>Topic:</b> {test.get('topic', 'N/A')}\n"
        text += f"📊 <b>Difficulty:</b> {test.get('difficulty', 'N/A').capitalize()}\n"
        text += f"❓ <b>Questions:</b> {len(test['questions'])}\n"
        text += f"⭐ <b>Total Points:</b> {sum(q['points'] for q in test['questions'])}\n"

        if test.get('description'):
            text += f"📄 <b>Description:</b> {test['description']}\n"

        text += f"\n━━━━━━━━━━━━━━━━━━━━━━━━\n"
        text += "📋 <b>QUESTIONS & ANSWERS</b>\n"
        text += "━━━━━━━━━━━━━━━━━━━━━━━━\n\n"

        # Show all questions
        labels = ['A', 'B', 'C', 'D', 'E', 'F']

        for i, question in enumerate(test['questions'], 1):
            text += f"<b>Q{i}:</b> {question['question_text']}\n\n"

            options = question['options']
            correct_idx = question['correct_option']

            for j, option in enumerate(options):
                if j < len(labels):
                    marker = " ✅" if j == correct_idx else ""
                    text += f"{labels[j]}) {option}{marker}\n"

            text += f"\n<i>Points: {question['points']}</i>\n"
            text += "\n━━━━━━━━━━━━━━━━━━━━━━━━\n\n"

        # Split message if too long (Telegram limit ~4096 characters)
        if len(text) > 4000:
            # Send in chunks
            chunks = []
            current_chunk = ""

            for line in text.split('\n'):
                if len(current_chunk) + len(line) + 1 > 4000:
                    chunks.append(current_chunk)
                    current_chunk = line + '\n'
                else:
                    current_chunk += line + '\n'

            if current_chunk:
                chunks.append(current_chunk)

            for chunk in chunks:
                await callback.message.answer(chunk, parse_mode="HTML")
        else:
            await callback.message.answer(text, parse_mode="HTML")

        # Show back button
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ Back", callback_data=f"select_test:{test_id}")]
        ])

        await callback.message.answer(
            "👆 Test content displayed above",
            reply_markup=keyboard
        )

    except Exception as e:
        logger.error(f"Error viewing test content: {e}")
        await callback.answer(f"❌ Error: {str(e)}", show_alert=True)


@router.callback_query(F.data.startswith("get_link:"))
async def get_test_link(callback: CallbackQuery):
    """Get shareable link and QR code for the test"""

    test_id = int(callback.data.split(":")[1])

    await callback.answer("🔗 Generating link...")

    try:
        # Check if test is published
        # We need to get assignments for this test
        import aiohttp

        # Get test details first
        test = await APIClient.get_test_preview(test_id)

        # Try to get assignment - if 404, test not published
        async with aiohttp.ClientSession() as session:
            async with session.get(f"http://127.0.0.1:8000/api/tests/{test_id}/") as response:
                if response.status == 200:
                    test_data = await response.json()

        # Check if test has assignments
        from django.conf import settings
        async with aiohttp.ClientSession() as session:
            # Get assignments for this test
            async with session.get(f"http://127.0.0.1:8000/api/assignments/?test_id={test_id}") as response:
                if response.status == 200:
                    assignments_data = await response.json()

                    if isinstance(assignments_data, list) and len(assignments_data) > 0:
                        # Test is published, get first assignment
                        assignment = assignments_data[0]
                        access_token = assignment['access_token']
                        bot_link = assignment['bot_link']

                        # Generate QR code
                        import qrcode
                        from io import BytesIO

                        qr = qrcode.QRCode(version=1, box_size=10, border=5)
                        qr.add_data(bot_link)
                        qr.make(fit=True)
                        qr_img = qr.make_image(fill_color="black", back_color="white")

                        # Save to bytes
                        bio = BytesIO()
                        qr_img.save(bio, 'PNG')
                        bio.seek(0)

                        # Build message
                        text = "━━━━━━━━━━━━━━━━━━━━━━━━\n"
                        text += "🔗 <b>TEST LINK</b>\n"
                        text += "━━━━━━━━━━━━━━━━━━━━━━━━\n\n"

                        text += f"📝 <b>Test:</b> {test['title']}\n"
                        text += f"🔑 <b>Token:</b> <code>{access_token}</code>\n\n"

                        text += "📤 <b>Share this link with students:</b>\n"
                        text += f"<code>{bot_link}</code>\n\n"

                        text += "📱 <b>QR Code attached below ⬇️</b>\n\n"
                        text += "💡 Students can click the link or scan the QR code to start the test automatically!"

                        # Send QR code as photo
                        from aiogram.types import BufferedInputFile

                        qr_file = BufferedInputFile(bio.getvalue(), filename=f"qr_{access_token}.png")

                        await callback.message.answer_photo(
                            photo=qr_file,
                            caption=text,
                            parse_mode="HTML"
                        )

                        # Show back button
                        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

                        keyboard = InlineKeyboardMarkup(inline_keyboard=[
                            [InlineKeyboardButton(text="⬅️ Back", callback_data=f"select_test:{test_id}")]
                        ])

                        await callback.message.answer(
                            "👆 Link and QR code sent above",
                            reply_markup=keyboard
                        )

                    else:
                        # Test not published
                        await callback.message.answer(
                            "❌ <b>Test Not Published</b>\n\n"
                            "This test hasn't been published yet.\n\n"
                            "Would you like to publish it now?",
                            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                                [InlineKeyboardButton(text="📤 Publish Now", callback_data=f"publish_test:{test_id}")],
                                [InlineKeyboardButton(text="⬅️ Back", callback_data=f"select_test:{test_id}")]
                            ]),
                            parse_mode="HTML"
                        )
                else:
                    raise Exception("Failed to check assignments")

    except Exception as e:
        logger.error(f"Error getting test link: {e}")
        await callback.answer(f"❌ Error: {str(e)}", show_alert=True)


@router.callback_query(F.data == "back_to_tests")
async def back_to_tests(callback: CallbackQuery, state: FSMContext):
    """Go back to My Tests list"""
    await callback.answer()

    # Re-show my tests
    await view_my_tests(callback.message, state)


@router.message(StateFilter(TeacherStates.MAIN_MENU), F.text == "📊 View Results")
async def view_results(message: Message, state: FSMContext):
    """View test results - show list of tests first"""

    processing_msg = await message.answer("⏳ Loading your tests...")

    try:
        tests_response = await APIClient.get_teacher_tests(message.from_user.id)

        await processing_msg.delete()

        if not tests_response or len(tests_response) == 0:
            await message.answer(
                "📊 <b>View Results</b>\n\n"
                "You haven't created any tests yet.\n\n"
                "Use <b>➕ Create Test</b> to get started!",
                parse_mode="HTML"
            )
            return

        # Create inline keyboard with test buttons
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

        buttons = []
        for test in tests_response[:10]:  # Show up to 10 recent tests
            # Get test title and ID
            test_title = test['title'][:40]  # Truncate if too long
            test_id = test['id']
            question_count = test.get('question_count', 0)

            button_text = f"📝 {test_title} ({question_count}Q)"
            buttons.append([
                InlineKeyboardButton(
                    text=button_text,
                    callback_data=f"view_results:{test_id}"
                )
            ])

        keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)

        await message.answer(
            "📊 <b>View Test Results</b>\n\n"
            "Select a test to view detailed results and statistics:",
            reply_markup=keyboard,
            parse_mode="HTML"
        )

        await state.set_state(TeacherStates.VIEWING_RESULTS)

    except Exception as e:
        logger.error(f"Error loading tests for results: {e}")
        await processing_msg.delete()
        await message.answer(
            f"❌ <b>Error:</b> {str(e)}",
            parse_mode="HTML"
        )


@router.callback_query(F.data.startswith("view_results:"))
async def show_test_results(callback: CallbackQuery, state: FSMContext):
    """Show detailed results for selected test"""

    test_id = int(callback.data.split(":")[1])

    await callback.answer("📊 Loading statistics...")

    try:
        stats = await APIClient.get_test_statistics(test_id)

        # Build results message
        test_info = stats['test']

        text = "━━━━━━━━━━━━━━━━━━━━━━━━\n"
        text += "📊 <b>TEST RESULTS</b>\n"
        text += "━━━━━━━━━━━━━━━━━━━━━━━━\n\n"

        text += f"📝 <b>Test:</b> {test_info['title']}\n"
        text += f"📚 <b>Topic:</b> {test_info.get('topic', 'N/A')}\n"
        text += f"📊 <b>Difficulty:</b> {test_info.get('difficulty', 'N/A').capitalize()}\n"
        text += f"❓ <b>Questions:</b> {test_info.get('question_count', 0)}\n\n"

        text += "━━━━━━━━━━━━━━━━━━━━━━━━\n"
        text += "📈 <b>STATISTICS</b>\n"
        text += "━━━━━━━━━━━━━━━━━━━━━━━━\n\n"

        total_students = stats['total_students']
        completed = stats['completed_attempts']

        text += f"👥 <b>Total Students:</b> {total_students}\n"
        text += f"✅ <b>Completed:</b> {completed}\n"

        if total_students > 0:
            avg_score = stats['average_score']
            avg_pct = stats['average_percentage']
            highest = stats['highest_score']
            lowest = stats['lowest_score']
            total_possible = stats['total_possible']

            text += f"\n📊 <b>Average Score:</b> {avg_score}/{total_possible} ({avg_pct}%)\n"
            text += f"🏆 <b>Highest Score:</b> {highest}/{total_possible}\n"
            text += f"📉 <b>Lowest Score:</b> {lowest}/{total_possible}\n"

            text += f"\n━━━━━━━━━━━━━━━━━━━━━━━━\n"
            text += f"👥 <b>TOP STUDENTS</b>\n"
            text += f"━━━━━━━━━━━━━━━━━━━━━━━━\n\n"

            # Show top students
            for student in stats['top_students'][:20]:
                rank = student['rank']
                name = student['student_name']
                score = student['score']
                total = student['total']
                pct = student['percentage']
                passed = student['passed']

                # Medal for top 3
                if rank == 1:
                    medal = "🥇"
                elif rank == 2:
                    medal = "🥈"
                elif rank == 3:
                    medal = "🥉"
                else:
                    medal = f"{rank}."

                status_icon = "✅" if passed else "❌"

                text += f"{medal} <b>{name}</b>\n"
                text += f"   Score: {score}/{total} ({pct}%) {status_icon}\n\n"

        else:
            text += "\n💡 No students have taken this test yet."

        await callback.message.answer(text, parse_mode="HTML")

    except Exception as e:
        logger.error(f"Error showing test results: {e}")

        # Check if it's a 404 (test not published)
        if "404" in str(e):
            await callback.message.answer(
                "❌ <b>No Results Available</b>\n\n"
                "This test hasn't been published yet or has no assignments.\n\n"
                "Please publish the test first using <b>📤 Publish & Share</b>",
                parse_mode="HTML"
            )
        else:
            await callback.answer(f"❌ Error: {str(e)}", show_alert=True)


@router.message(StateFilter(TeacherStates.MAIN_MENU), F.text == "🏆 Leaderboard")
async def view_leaderboard_teacher(message: Message):
    """View leaderboard"""
    await message.answer(
        "🏆 <b>Leaderboard</b>\n\n"
        "This feature is coming soon!\n\n"
        "You'll see top performers across all your tests.",
        parse_mode="HTML"
    )


# ============================================
# BACK TO MAIN MENU
# ============================================

@router.message(F.text == "🏠 Main Menu")
async def back_to_main_menu(message: Message, state: FSMContext):
    """Return to main menu"""
    current_state = await state.get_state()

    if current_state and "Teacher" in current_state:
        await state.set_state(TeacherStates.MAIN_MENU)
        await message.answer(
            "🏠 Main Menu",
            reply_markup=get_teacher_main_menu()
        )
    else:
        await message.answer("Use /start to begin")