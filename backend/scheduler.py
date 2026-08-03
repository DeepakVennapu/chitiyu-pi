# backend/scheduler.py
import asyncio, logging
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from config import DB_PATH, TELEGRAM_CHAT_ID, TELEGRAM_BOT_TOKEN

logger = logging.getLogger(__name__)


def _flush_event(domain: str, event_type: str, text: str, user_id: int = 1) -> None:
    from telegram import Bot
    from db.connection import get_connection
    from db.schema import initialize_schema
    from orchestrator.dispatcher import post_event, dispatch_pending
    conn = get_connection(DB_PATH)
    initialize_schema(conn)
    post_event(conn, user_id, domain, event_type,
               {"text": text, "chat_id": TELEGRAM_CHAT_ID})
    async def _dispatch():
        async with Bot(TELEGRAM_BOT_TOKEN) as bot:
            await dispatch_pending(conn, bot)
    asyncio.run(_dispatch())
    conn.close()


def _morning_digest() -> None:
    try:
        from db.connection import get_connection
        from db.schema import initialize_schema
        from domains.tasks.db import get_overdue_tasks, get_today_tasks
        from domains.health.db import get_metrics_for_date
        from datetime import datetime, timezone, timedelta
        from config import CALENDAR_ICS_URL
        from integrations.calendar import fetch_today_events
        conn = get_connection(DB_PATH)
        initialize_schema(conn)
        yesterday = (datetime.now(timezone.utc).date() - timedelta(days=1)).isoformat()
        overdue = get_overdue_tasks(conn, 1)
        today_tasks = get_today_tasks(conn, 1)
        metrics = get_metrics_for_date(conn, 1, yesterday)
        conn.close()
        calendar_events = fetch_today_events(CALENDAR_ICS_URL)
        lines = ["Good morning, Deep"]
        if metrics:
            lines.append(f"Sleep: {metrics.get('sleep_deep_mins','—')}min deep, "
                         f"{metrics.get('sleep_total_mins','—')}min total, "
                         f"HR {metrics.get('resting_hr','—')}")
        lines.append(f"Tasks: {len(overdue)} overdue, {len(today_tasks)} due today")
        if calendar_events:
            cal_lines = [f"- {e['title']} at {e['start_time']}" for e in calendar_events]
            lines.append("Today's Calendar:\n" + "\n".join(cal_lines))
        _flush_event("orchestrator", "morning_digest", "\n".join(lines))
    except Exception:
        logger.exception("morning digest failed")


def _meal_nudge() -> None:
    try:
        from db.connection import get_connection
        from db.schema import initialize_schema
        from domains.health.db import get_today_meals
        from datetime import datetime, timezone, timedelta
        conn = get_connection(DB_PATH)
        initialize_schema(conn)
        meals = get_today_meals(conn, 1)
        conn.close()
        if not meals:
            _flush_event("health", "meal_nudge", "Did you eat anything? Log your last meal.")
            return
        last_meal_time = datetime.fromisoformat(meals[-1]["logged_at"].replace("Z", "+00:00"))
        if last_meal_time.tzinfo is None:
            last_meal_time = last_meal_time.replace(tzinfo=timezone.utc)
        if datetime.now(timezone.utc) - last_meal_time > timedelta(hours=1):
            _flush_event("health", "meal_nudge", "No meal logged in the past hour. Did you eat?")
    except Exception:
        logger.exception("meal nudge failed")


def _midday_nudge() -> None:
    try:
        from db.connection import get_connection
        from db.schema import initialize_schema
        from domains.tasks.db import get_overdue_tasks
        from domains.tasks.formatter import format_overdue_nudge
        conn = get_connection(DB_PATH)
        initialize_schema(conn)
        overdue = get_overdue_tasks(conn, 1)
        conn.close()
        if overdue:
            _flush_event("tasks", "overdue_nudge", format_overdue_nudge(overdue))
    except Exception:
        logger.exception("midday nudge failed")


def _evening_prompt() -> None:
    try:
        from db.connection import get_connection
        from db.schema import initialize_schema
        from domains.journal.db import get_entry
        from datetime import datetime
        from zoneinfo import ZoneInfo
        conn = get_connection(DB_PATH)
        initialize_schema(conn)
        today = datetime.now(ZoneInfo("America/New_York")).date().isoformat()
        existing = get_entry(conn, 1, today)
        if not existing:
            conn.execute(
                "INSERT OR REPLACE INTO pending_state(user_id, type, payload) VALUES (?,?,?)",
                (1, "evening_summary", '{}')
            )
            conn.commit()
        conn.close()
        if not existing:
            _flush_event("journal", "retro_prompt", "How was today? Anything to capture?")
    except Exception:
        logger.exception("evening prompt failed")


def _evening_followup() -> None:
    try:
        from db.connection import get_connection
        from db.schema import initialize_schema
        from domains.journal.db import get_entry
        from datetime import datetime
        from zoneinfo import ZoneInfo
        conn = get_connection(DB_PATH)
        initialize_schema(conn)
        today = datetime.now(ZoneInfo("America/New_York")).date().isoformat()
        existing = get_entry(conn, 1, today)
        conn.close()
        if not existing:
            _flush_event("journal", "retro_followup", "Still up? Just a few words about today is fine.")
    except Exception:
        logger.exception("evening followup failed")


def build_scheduler() -> BackgroundScheduler:
    sched = BackgroundScheduler(timezone="America/New_York")
    sched.add_job(_morning_digest,   CronTrigger(hour=8,        minute=0),  id="morning_digest")
    sched.add_job(_meal_nudge,       CronTrigger(hour="9-22",   minute=0),  id="meal_nudge")
    sched.add_job(_midday_nudge,     CronTrigger(hour=16,       minute=0),  id="midday_nudge")
    sched.add_job(_evening_prompt,   CronTrigger(hour=22,       minute=0),  id="evening_prompt")
    sched.add_job(_evening_followup, CronTrigger(hour=22,       minute=30), id="evening_followup")
    return sched
