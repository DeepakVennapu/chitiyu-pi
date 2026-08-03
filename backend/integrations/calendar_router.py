# backend/integrations/calendar_router.py
from fastapi import APIRouter, Depends
from auth import verify_api_key
from config import CALENDAR_ICS_URL
from integrations.calendar import fetch_today_events

router = APIRouter(prefix="/integrations/calendar", tags=["calendar"])


@router.get("/today")
def get_calendar_today(_: None = Depends(verify_api_key)) -> list[dict]:
    """
    Return today's calendar events from the configured ICS feed.

    Returns an empty list if CALENDAR_ICS_URL is not set or the feed is
    unreachable — never errors.
    """
    return fetch_today_events(CALENDAR_ICS_URL)
