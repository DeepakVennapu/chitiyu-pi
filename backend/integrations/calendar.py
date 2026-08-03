# backend/integrations/calendar.py
"""
Read-only iCal/Google Calendar integration.

fetch_today_events(ics_url) returns today's events as a list of dicts.
Fails silently on any error — never raises, never breaks the digest.
"""
from __future__ import annotations

import datetime as _dt
import urllib.request
from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

LOCAL_TZ = ZoneInfo("America/New_York")


def fetch_today_events(ics_url: str) -> list[dict]:
    """
    Fetch today's events from an iCal/Google Calendar ICS feed.

    Args:
        ics_url: Public ICS URL. If empty string, returns [] immediately.

    Returns:
        List of {"title": str, "start_time": str, "end_time": str} for today's events,
        sorted by start_time. Returns [] on any error.
    """
    if not ics_url:
        return []

    try:
        from icalendar import Calendar
        import urllib.request

        with urllib.request.urlopen(ics_url, timeout=5) as response:
            raw = response.read()

        cal = Calendar.from_ical(raw)
        today = date.today()
        events: list[dict] = []

        for component in cal.walk():
            if component.name != "VEVENT":
                continue

            dtstart = component.get("DTSTART")
            dtend = component.get("DTEND")
            summary = str(component.get("SUMMARY", ""))

            if dtstart is None:
                continue

            start_val = dtstart.dt
            end_val = dtend.dt if dtend else start_val

            # Handle all-day events (date, not datetime)
            if isinstance(start_val, _dt.date) and not isinstance(start_val, _dt.datetime):
                if start_val == today:
                    events.append({
                        "title": summary,
                        "start_time": "00:00",
                        "end_time": "23:59",
                    })
                continue

            # Datetime events: convert to local timezone
            if start_val.tzinfo is not None:
                start_local = start_val.astimezone(LOCAL_TZ)
            else:
                start_local = start_val.replace(tzinfo=LOCAL_TZ)

            if isinstance(end_val, _dt.datetime):
                if end_val.tzinfo is not None:
                    end_local = end_val.astimezone(LOCAL_TZ)
                else:
                    end_local = end_val.replace(tzinfo=LOCAL_TZ)
            else:
                end_local = start_local

            if start_local.date() == today:
                events.append({
                    "title": summary,
                    "start_time": start_local.strftime("%H:%M"),
                    "end_time": end_local.strftime("%H:%M"),
                })

        return sorted(events, key=lambda e: e["start_time"])

    except Exception:
        # Fail silently — calendar is optional. Log to stderr for debugging.
        import traceback
        traceback.print_exc()
        return []
