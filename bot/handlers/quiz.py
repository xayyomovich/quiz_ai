from aiogram import Router, types, F
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
import aiohttp

router = Router()

# Replace with your Django API endpoint
DJANGO_API_URL = "http://127.0.0.1:8000/api/quiz/next/"

# Store user quiz progress (simple version)
user_progress = {}

@router.message(F.text.lower() == "start quiz")
async def start_quiz(message: types.Message):
    user_id = message.from_user.id
    user_progress[user_id] = {"current_question": 1}
    await send_question(message, user_id)


async def send_question(message: types.Message, user_id: int):
    question_id = user_progress[user_id]["current_question"]

    async with aiohttp.ClientSession() as session:
        async with session.get(f"{DJANGO_API_URL}?q={question_id}") as response:
            if response.status == 200:
                data = await response.json()
                question = data.get("question")
                options = data.get("options")

                # Build keyboard
                keyboard = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text=opt, callback_data=opt)] for opt in options
                ])

                await message.answer(question, reply_markup=keyboard)
            else:
                await message.answer("❌ Error fetching question from backend.")


@router.callback_query()
async def handle_answer(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    selected_answer = callback.data

    # Here you can validate answer via Django API if you want
    await callback.answer(f"You selected: {selected_answer}")

    # Move to next question
    user_progress[user_id]["current_question"] += 1
    await send_question(callback.message, user_id)
