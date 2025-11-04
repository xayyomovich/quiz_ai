import asyncio, os, sys, django, logging
from aiogram import Bot, Dispatcher
from aiogram.types import BotCommand
from aiogram.fsm.storage.memory import MemoryStorage

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Add Django project root to sys.path
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
# Set Django settings module
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "aiquiz_project.settings")
# Initialize Django
django.setup()

# Now import token from settings
from django.conf import settings

BOT_TOKEN = settings.BOT_TOKEN

# Import handlers
from bot.handlers import start, teacher, student

# Create bot and dispatcher
bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# Register routers (ORDER MATTERS!)
# Start handler MUST be first to catch deep links
dp.include_router(start.router)  # Handles /start and deep links
dp.include_router(teacher.router)  # Teacher-specific handlers
dp.include_router(student.router)  # Student-specific handlers


async def set_bot_commands(bot: Bot):
    """Set bot commands menu"""
    commands = [
        BotCommand(command="start", description="Start bot / Restart"),
    ]
    await bot.set_my_commands(commands)


async def main():
    print("=" * 60)
    print("🚀 AI QUIZBOT STARTING...")
    print("=" * 60)
    print(f"✅ Django configured")
    print(f"✅ Bot token loaded: {BOT_TOKEN[:10]}...")
    print(f"✅ Handlers registered: teacher, student")
    print(f"✅ FSM storage: MemoryStorage")
    print("=" * 60)

    # Set commands
    await set_bot_commands(bot)

    print("✅ Bot is running! Send /start in Telegram")
    print("⚠️  Press Ctrl+C to stop")
    print("=" * 60)

    # Start polling
    try:
        await dp.start_polling(bot, skip_updates=True)
    finally:
        await bot.session.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n" + "=" * 60)
        print("⚠️  Bot stopped by user")
        print("=" * 60)