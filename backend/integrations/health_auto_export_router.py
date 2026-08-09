# backend/integrations/health_auto_export_router.py
"""
Health Auto Export REST API endpoint.

Health Auto Export (iOS app) POSTs a JSON payload shaped like:
  {"data": {"metrics": [{"name": "...", "units": "...", "data": [{"date": "...", "qty": ...}]}]}}

This endpoint parses the known metric names for steps, sleep, and resting HR,
groups entries by date (summing / averaging as appropriate), and calls
upsert_health_metrics for each date found.

Metric names to handle:
  - "step_count" (count)   → steps
  - "resting_heart_rate"   → resting_hr (bpm, rounded)
  - "sleep_analysis"       → sleep_total_mins (sum of all stages)
                             sleep_deep_mins (sum of "asleep_deep" entries only)

The "date" field on each data point is an ISO 8601 string like "2026-08-08 00:00:00 +0000"
or "2026-08-08T00:00:00+00:00". We parse the date portion only.
"""
from __future__ import annotations

import re
import sqlite3
from collections import defaultdict
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from auth import verify_api_key
from config import DB_PATH
from db.connection import get_connection
from db.schema import initialize_schema
from domains.health.db import upsert_health_metrics

router = APIRouter(prefix="/integrations", tags=["integrations"])

_DATE_RE = re.compile(r"(\d{4}-\d{2}-\d{2})")


def _parse_date(raw: str) -> str | None:
    m = _DATE_RE.search(raw)
    return m.group(1) if m else None


def _get_conn():
    c = get_connection(DB_PATH)
    initialize_schema(c)
    try:
        yield c
    finally:
        c.close()


class HaePayload(BaseModel):
    data: dict[str, Any]
    user_id: int = 1


@router.post("/health-auto-export")
def health_auto_export(
    payload: HaePayload,
    _: None = Depends(verify_api_key),
    conn: sqlite3.Connection = Depends(_get_conn),
) -> dict:
    """Receive a Health Auto Export REST API push and persist the data."""
    metrics_list: list[dict] = payload.data.get("metrics", [])

    # Accumulators keyed by date string
    steps_by_date: dict[str, int] = defaultdict(int)
    sleep_total_by_date: dict[str, float] = defaultdict(float)
    sleep_deep_by_date: dict[str, float] = defaultdict(float)
    hr_readings: dict[str, list[float]] = defaultdict(list)

    for metric in metrics_list:
        name: str = metric.get("name", "").lower()
        data_points: list[dict] = metric.get("data", [])

        for point in data_points:
            raw_date = point.get("date", "")
            date = _parse_date(raw_date)
            if not date:
                continue
            qty = point.get("qty")
            if qty is None:
                continue

            if name == "step_count":
                steps_by_date[date] += int(qty)

            elif name == "resting_heart_rate":
                hr_readings[date].append(float(qty))

            elif name == "sleep_analysis":
                source = (point.get("source") or "").lower()
                sleep_stage = (point.get("value") or point.get("sleepStage") or "").lower()
                duration_mins = float(qty)  # Health Auto Export exports in hours; convert below
                units = metric.get("units", "").lower()
                if "hr" in units or "hour" in units:
                    duration_mins = duration_mins * 60

                # Sum all sleep stages (InBed, Asleep, REM, Core, Deep) as total
                # We only track Deep sleep separately
                sleep_total_by_date[date] += duration_mins
                if "deep" in sleep_stage or "asleep_deep" in sleep_stage:
                    sleep_deep_by_date[date] += duration_mins

    # Merge all dates encountered
    all_dates = set(steps_by_date) | set(hr_readings) | set(sleep_total_by_date)
    if not all_dates:
        return {"ok": True, "dates_synced": 0, "message": "No parseable data in payload"}

    for date in sorted(all_dates):
        steps = steps_by_date.get(date) or None
        resting_hr = (
            round(sum(hr_readings[date]) / len(hr_readings[date]))
            if hr_readings.get(date) else None
        )
        sleep_total = round(sleep_total_by_date[date]) if sleep_total_by_date.get(date) else None
        sleep_deep = round(sleep_deep_by_date[date]) if sleep_deep_by_date.get(date) else None
        upsert_health_metrics(conn, payload.user_id, date, steps, sleep_deep, sleep_total, resting_hr)

    return {"ok": True, "dates_synced": len(all_dates), "dates": sorted(all_dates)}
