# backend/config.py
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(override=True)

BASE_DIR = Path(__file__).parent.parent
DB_PATH = str(BASE_DIR / os.environ.get("DB_FILENAME", "chitiyu.db"))
API_KEY = os.environ["API_KEY"]
TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
TELEGRAM_CHAT_ID = int(os.environ["TELEGRAM_CHAT_ID"])
HA_URL = os.environ.get("HA_URL", "")
HA_TOKEN = os.environ.get("HA_TOKEN", "")
OWNER_NAME = os.environ.get("OWNER_NAME", "Deep")
CLAUDE_BIN = os.environ.get("CLAUDE_BIN", "claude")
CALENDAR_ICS_URL = os.environ.get("CALENDAR_ICS_URL", "")  # Plan 4 — iCal/Google feed URL
DISPATCH_MODEL = "claude-haiku-4-5-20251001"
POLISH_MODEL = "claude-sonnet-4-6"
RENPHO_EMAIL = os.getenv("RENPHO_EMAIL", "")
RENPHO_PASSWORD = os.getenv("RENPHO_PASSWORD", "")
