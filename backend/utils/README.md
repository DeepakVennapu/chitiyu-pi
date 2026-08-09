# utils

Shared utilities for the backend. Import from here rather than inlining in domain code.

## local_time.py

Single source of truth for local-time operations. The server runs in MDT (UTC-6); all date comparisons and storage must use system local time, not UTC.

| Function | Returns | Use for |
|----------|---------|---------|
| `local_now()` | tz-aware `datetime` in system local TZ | Default timestamps on inserts |
| `today_local()` | `str` (`YYYY-MM-DD`) | "Today" date for DB queries |
| `to_local_ts(iso)` | `str` (`YYYY-MM-DD HH:MM:SS`) | Converting incoming UTC ISO strings before storage |
| `this_month_local()` | `(year_str, month_str)` | Current month for budget/spend queries |

**Rule:** Never use `datetime.now(timezone.utc)` for anything user-facing. UTC is only appropriate for internal scheduling internals (e.g. APScheduler trigger math).
