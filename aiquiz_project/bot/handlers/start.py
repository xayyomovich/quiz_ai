from aiogram import Router, types
from aiogram.filters import Command

router = Router()

@router.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer(
        "Salom! 👋 Men AI QuizBotman.\n\n"
        "Iltimos, kimligingizni tanlang:",
        reply_markup=types.ReplyKeyboardMarkup(
            keyboard=[
                [types.KeyboardButton(text="👨‍🏫 Teacher")],
                [types.KeyboardButton(text="👩‍🎓 Student")],
            ],
            resize_keyboard=True
        )
    )
