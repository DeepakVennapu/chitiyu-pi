# tests/test_calendar.py
"""
Calendar integration tests using an inline ICS fixture string.
No external network calls — all tests are offline.
"""
from __future__ import annotations
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

from unittest.mock import patch, MagicMock
from datetime import date
import io

# ---------------------------------------------------------------------------
# Inline ICS fixture — two events on 2026-08-02, one on a different day
# ---------------------------------------------------------------------------
ICS_FIXTURE = """\
BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Test//Test//EN
BEGIN:VEVENT
DTSTART;TZID=America/New_York:20260802T090000
DTEND;TZID=America/New_York:20260802T100000
SUMMARY:Morning standup
END:VEVENT
BEGIN:VEVENT
DTSTART;TZID=America/New_York:20260802T140000
DTEND;TZID=America/New_York:20260802T150000
SUMMARY:Doctor appointment
END:VEVENT
BEGIN:VEVENT
DTSTART;TZID=America/New_York:20260803T090000
DTEND;TZID=America/New_York:20260803T100000
SUMMARY:Tomorrow event — should not appear
END:VEVENT
BEGIN:VEVENT
DTSTART;VALUE=DATE:20260802
DTEND;VALUE=DATE:20260803
SUMMARY:All-day meeting
END:VEVENT
END:VCALENDAR
""".encode()

ICS_URL = "https://calendar.example.com/basic.ics"


def _mock_urlopen(raw_bytes: bytes):
    """Return a context-manager mock that yields a response with .read()."""
    mock_resp = MagicMock()
    mock_resp.read.return_value = raw_bytes
    mock_resp.__enter__ = lambda s: s
    mock_resp.__exit__ = MagicMock(return_value=False)
    return mock_resp


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_empty_url_returns_empty_list():
    from integrations.calendar import fetch_today_events
    assert fetch_today_events("") == []


def test_fetch_today_events_returns_todays_events():
    from integrations.calendar import fetch_today_events
    target_date = date(2026, 8, 2)

    with patch("integrations.calendar.date") as mock_date, \
         patch("urllib.request.urlopen", return_value=_mock_urlopen(ICS_FIXTURE)):
        mock_date.today.return_value = target_date
        mock_date.side_effect = lambda *args, **kwargs: date(*args, **kwargs)

        events = fetch_today_events(ICS_URL)

    titles = [e["title"] for e in events]
    assert "Morning standup" in titles
    assert "Doctor appointment" in titles
    assert "Tomorrow event — should not appear" not in titles


def test_fetch_today_events_sorted_by_start():
    from integrations.calendar import fetch_today_events
    target_date = date(2026, 8, 2)

    with patch("integrations.calendar.date") as mock_date, \
         patch("urllib.request.urlopen", return_value=_mock_urlopen(ICS_FIXTURE)):
        mock_date.today.return_value = target_date
        mock_date.side_effect = lambda *args, **kwargs: date(*args, **kwargs)

        events = fetch_today_events(ICS_URL)

    timed = [e for e in events if e["start_time"] not in ("00:00",)]
    assert timed == sorted(timed, key=lambda e: e["start_time"])


def test_fetch_allday_event_included():
    from integrations.calendar import fetch_today_events
    target_date = date(2026, 8, 2)

    with patch("integrations.calendar.date") as mock_date, \
         patch("urllib.request.urlopen", return_value=_mock_urlopen(ICS_FIXTURE)):
        mock_date.today.return_value = target_date
        mock_date.side_effect = lambda *args, **kwargs: date(*args, **kwargs)

        events = fetch_today_events(ICS_URL)

    titles = [e["title"] for e in events]
    assert "All-day meeting" in titles


def test_fetch_network_error_returns_empty_list():
    from integrations.calendar import fetch_today_events

    with patch("urllib.request.urlopen", side_effect=OSError("network down")):
        result = fetch_today_events(ICS_URL)

    assert result == []


def test_fetch_malformed_ics_returns_empty_list():
    from integrations.calendar import fetch_today_events
    bad_bytes = b"this is not valid ics data %%%"

    with patch("urllib.request.urlopen", return_value=_mock_urlopen(bad_bytes)):
        result = fetch_today_events(ICS_URL)

    assert result == []


def test_event_dict_shape():
    from integrations.calendar import fetch_today_events
    target_date = date(2026, 8, 2)

    with patch("integrations.calendar.date") as mock_date, \
         patch("urllib.request.urlopen", return_value=_mock_urlopen(ICS_FIXTURE)):
        mock_date.today.return_value = target_date
        mock_date.side_effect = lambda *args, **kwargs: date(*args, **kwargs)

        events = fetch_today_events(ICS_URL)

    for e in events:
        assert "title" in e
        assert "start_time" in e
        assert "end_time" in e
        assert isinstance(e["title"], str)
        # Times are HH:MM format
        assert len(e["start_time"]) == 5
        assert e["start_time"][2] == ":"
