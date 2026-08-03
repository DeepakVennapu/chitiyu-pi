# backend/scheduler.py
import logging
from apscheduler.schedulers.background import BackgroundScheduler

logger = logging.getLogger(__name__)


def build_scheduler() -> BackgroundScheduler:
    """Build and return the APScheduler instance with all jobs registered."""
    sched = BackgroundScheduler(timezone="UTC")
    # Jobs are registered here (digest, reminders, etc.)
    # Placeholder — jobs will be added in later tasks.
    logger.info("Scheduler built with %d jobs", len(sched.get_jobs()))
    return sched
