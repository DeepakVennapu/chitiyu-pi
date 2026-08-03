# backend/bot/telegram.py
import logging
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters
from bot.handlers import handle_text, cmd_start, handle_photo
from config import TELEGRAM_BOT_TOKEN

logger = logging.getLogger(__name__)


def build_app():
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    return app


def run_bot():
    app = build_app()
    logger.info("Telegram bot starting...")
    app.run_polling()
