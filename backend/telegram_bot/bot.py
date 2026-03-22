"""
TruthCrew Telegram bot — application builder.

Registers all handlers, menu commands, and bot description via post_init.
Integrated into FastAPI lifespan (server/api.py) for single-process startup.
"""

import os
import asyncio
import logging

from telegram import BotCommand
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
)

from telegram_bot.handlers import (
    start,
    help_cmd,
    check,
    trending,
    language_cmd,
    handle_message,
    handle_callback_query,
)

logger = logging.getLogger(__name__)


# ── Bot commands shown in the Telegram Menu button ───────────────────────────
BOT_COMMANDS = [
    BotCommand("check",    "🔍 Analyse a claim"),
    BotCommand("trending", "🔥 Top trending misinformation"),
    BotCommand("language", "🌐 Change response language"),
    BotCommand("help",     "📖 Show all commands"),
    BotCommand("start",    "👋 Welcome & usage"),
]

BOT_DESCRIPTION = (
    "TruthCrew is your AI-powered misinformation detector. "
    "Send any claim or news headline and I'll fact-check it instantly using "
    "trusted sources and AI analysis.\n\n"
    "✅ Verify claims in seconds\n"
    "🔥 See trending misinformation\n"
    "🌍 Know which regions are most affected\n"
    "📰 View actual sources used for verification\n"
    "🌐 Responses in English, Hindi & Marathi"
)

BOT_SHORT_DESCRIPTION = (
    "AI-powered fact-checker — verify claims, spot misinformation, see sources."
)


def build_application() -> Application:
    """
    Build and configure the Telegram Application instance.
    Called by the FastAPI lifespan to integrate bot startup/shutdown.
    """
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise ValueError(
            "TELEGRAM_BOT_TOKEN is not set. "
            "Add it to your .env file and restart the server."
        )

    app = Application.builder().token(token).build()

    # ── Command handlers ──
    app.add_handler(CommandHandler("start",    start))
    app.add_handler(CommandHandler("help",     help_cmd))
    app.add_handler(CommandHandler("check",    check))
    app.add_handler(CommandHandler("trending", trending))
    app.add_handler(CommandHandler("language", language_cmd))

    # ── Inline button callbacks (language switching + preference setting) ──
    app.add_handler(CallbackQueryHandler(handle_callback_query))

    # ── Natural language / plain text ──
    app.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message)
    )

    logger.info("✅ Telegram bot application built — all handlers registered")
    return app


# ── Standalone entrypoint (development) ──────────────────────────────────────

async def _run_standalone():
    """Run the bot in polling mode as a standalone process."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )
    from dotenv import load_dotenv
    load_dotenv()

    app = build_application()
    logger.info("🤖 Starting TruthCrew bot in STANDALONE polling mode...")
    await app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    asyncio.run(_run_standalone())
