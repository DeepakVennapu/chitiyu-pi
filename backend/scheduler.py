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
    """8am: build cross-domain digest and send via Telegram."""
    from db.connection import get_connection
    from db.schema import initialize_schema
    from orchestrator.digest import build_morning_digest
    from config import DB_PATH

    conn = get_connection(DB_PATH)
    initialize_schema(conn)
    try:
        user_id = 1  # Phase 1: solo user
        text = build_morning_digest(conn, user_id)
        _flush_event("orchestrator", "morning_digest", text, user_id)
    except Exception as exc:
        import logging
        logging.getLogger(__name__).error("morning digest failed: %s", exc)
    finally:
        conn.close()


def _meal_nudge() -> None:
    try:
        from db.connection import get_connection
        from db.schema import initialize_schema
        from domains.health.db import get_today_meals
        from datetime import timedelta
        from utils.local_time import local_now, to_local_ts
        conn = get_connection(DB_PATH)
        initialize_schema(conn)
        meals = get_today_meals(conn, 1)
        conn.close()
        if not meals:
            _flush_event("health", "meal_nudge", "Did you eat anything? Log your last meal.")
            return
        # logged_at is stored as bare local "YYYY-MM-DD HH:MM:SS" — parse as local
        from datetime import datetime
        raw_ts = meals[-1]["logged_at"].replace(" ", "T")
        last_meal_time = datetime.fromisoformat(raw_ts).astimezone()
        if local_now() - last_meal_time > timedelta(hours=1):
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
        from utils.local_time import today_local
        conn = get_connection(DB_PATH)
        initialize_schema(conn)
        today = today_local()
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
        from utils.local_time import today_local
        conn = get_connection(DB_PATH)
        initialize_schema(conn)
        today = today_local()
        existing = get_entry(conn, 1, today)
        conn.close()
        if not existing:
            _flush_event("journal", "retro_followup", "Still up? Just a few words about today is fine.")
    except Exception:
        logger.exception("evening followup failed")


def _renpho_sync() -> None:
    """7am: sync latest weight measurement from Renpho scale."""
    from db.connection import get_connection
    from db.schema import initialize_schema
    from domains.health.renpho import sync_renpho_weight

    conn = get_connection(DB_PATH)
    initialize_schema(conn)
    try:
        result = sync_renpho_weight(conn, user_id=1)
        if result:
            logger.info("Renpho sync complete: %.1f kg", result["weight_kg"])
    except Exception:
        logger.exception("Renpho sync job failed")
    finally:
        try:
            conn.close()
        except Exception:
            pass


def build_scheduler() -> BackgroundScheduler:
    import datetime as _dt
    _local_tz = _dt.datetime.now().astimezone().tzinfo
    sched = BackgroundScheduler(timezone=_local_tz)
    sched.add_job(_renpho_sync,      CronTrigger(hour=7,        minute=0),  id="renpho_sync")
    sched.add_job(_morning_digest,   CronTrigger(hour=8,        minute=0),  id="morning_digest")
    # sched.add_job(_meal_nudge,       CronTrigger(hour="9-22",   minute=0),  id="meal_nudge")  # disabled
    sched.add_job(_midday_nudge,     CronTrigger(hour=16,       minute=0),  id="midday_nudge")
    sched.add_job(_evening_prompt,   CronTrigger(hour=22,       minute=0),  id="evening_prompt")
    sched.add_job(_evening_followup, CronTrigger(hour=22,       minute=30), id="evening_followup")
    return sched
