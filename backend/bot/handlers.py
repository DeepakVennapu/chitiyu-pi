# backend/bot/handlers.py
import logging
from telegram import Update
from telegram.ext import ContextTypes
from db.connection import get_connection
from db.schema import initialize_schema
from orchestrator.handler import handle_message
from orchestrator.history import HistoryManager
from config import DB_PATH

logger = logging.getLogger(__name__)
_history = HistoryManager()
USER_ID = 1  # MVP single user


def _conn():
    c = get_connection(DB_PATH)
    initialize_schema(c)
    return c


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message.text
    conn = _conn()
    try:
        _history.append("user", message)
        history_snap = _history.get()
        reply = handle_message(conn, USER_ID, message, history=history_snap[:-1])
        _history.append("assistant", reply)
        for chunk in _split(reply):
            await update.message.reply_text(chunk)
    except Exception as e:
        logger.exception("handle_text failed")
        await update.message.reply_text("Something went wrong. Try again.")
    finally:
        conn.close()


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Chitiyu online. What can I help with?")


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Photo scanning isn't supported yet. Log meals as text.")


def _split(text: str, limit: int = 4096) -> list[str]:
    if len(text) <= limit:
        return [text]
    chunks = []
    while text:
        chunks.append(text[:limit])
        text = text[limit:]
    return chunks
