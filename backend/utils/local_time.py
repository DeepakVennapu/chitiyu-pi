from datetime import datetime, date


def local_now() -> datetime:
    """Current local datetime (timezone-aware, system TZ)."""
    return datetime.now().astimezone()


def today_local() -> str:
    """Today's date as YYYY-MM-DD in system local time."""
    return local_now().date().isoformat()


def to_local_ts(iso: str) -> str:
    """Convert any ISO 8601 string (with or without Z/offset) to 'YYYY-MM-DD HH:MM:SS' in system local time.
    Bare strings (no tz info) are passed through unchanged — assumed already local."""
    dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        return iso[:19].replace("T", " ")
    return dt.astimezone().strftime("%Y-%m-%d %H:%M:%S")


def this_month_local() -> tuple[str, str]:
    """Returns (year_str, month_str) for the current local month, e.g. ('2026', '8')."""
    d = local_now().date()
    return str(d.year), str(d.month)
