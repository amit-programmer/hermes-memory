"""
bot.py - Direct Telegram Bot Runner
Can be run via `python bot.py` or through the FastAPI server (`python main.py`).
All credentials and configuration are strictly loaded from .env.
"""
import asyncio
from bot.telegram_bot import create_bot_application
from core.brain import brain
from utils.helpers import Config, logger


async def run_bot():
    """Initialize memory tiers and start the Telegram bot."""
    logger.info("Initializing Hermes Brain (Redis + Turso + Supabase)...")
    await brain.initialize()

    app = create_bot_application()
    if not app:
        logger.error("Cannot start Telegram bot: TELEGRAM_BOT_TOKEN missing in .env")
        return

    logger.info("Starting Telegram Bot polling (drop_pending_updates=True)...")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    asyncio.run(run_bot())
