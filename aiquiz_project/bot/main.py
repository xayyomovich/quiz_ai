import asyncio, os, sys, django
from aiogram import Bot, Dispatcher
from aiogram.types import BotCommand

from bot.handlers import start, quiz
from bot.loader import bot, dp

# Add Django project root to sys.path
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
# Set Django settings module
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "aiquiz_project.settings")
# Initialize Django
django.setup()

# Now import token from settings
from django.conf import settings
BOT_TOKEN = settings.BOT_TOKEN

# Create bot and dispatcher
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Register handlers
dp.include_router(start.router)
dp.include_router(quiz.router)


async def main():
    print("Bot is running...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
