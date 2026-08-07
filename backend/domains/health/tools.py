import json, re, sqlite3
from datetime import datetime, timezone
from orchestrator.llm import call_claude
from domains.health.db import insert_meal, get_today_meals, get_metrics_for_date, upsert_health_metrics
from domains.health.formatter import format_today_summary, format_meal_confirmation, TARGETS
from config import DISPATCH_MODEL

_PARSE_PROMPT = """\
Parse this meal description into macros. Return JSON only:
{{"description": "<clean name>", "calories": <int>, "protein": <float>, "fat": <float>, "carbs": <float>}}
Context (if any): {context}
Meal: {text}"""


def parse_meal_macros(text: str, context: str = "") -> dict | None:
    """Call Claude to parse meal text into macros. Returns dict or None on failure."""
    raw = call_claude(_PARSE_PROMPT.format(text=text, context=context),
                      model=DISPATCH_MODEL, timeout=20)
    m = re.search(r'\{.*\}', raw, re.DOTALL)
    if not m:
        return None
    return json.loads(m.group())


def log_meal(conn: sqlite3.Connection, user_id: int, text: str, context: str = "") -> str:
    data = parse_meal_macros(text, context)
    if data is None:
        return "Couldn't parse that meal. Try: '2 eggs, toast, coffee'."
    insert_meal(conn, user_id, data["description"], data["calories"],
                data["protein"], data.get("fat"), data.get("carbs"))
    result = format_meal_confirmation(data["description"], data["calories"], data["protein"])

    # Trigger async insight regeneration — non-blocking
    try:
        from orchestrator.insights import trigger_insights_async
        trigger_insights_async(user_id, scope="today")
    except Exception:
        pass  # Never let insight trigger block the meal log response

    return result


def get_today_meals_tool(conn: sqlite3.Connection, user_id: int) -> str:
    meals = get_today_meals(conn, user_id)
    today = datetime.now(timezone.utc).date().isoformat()
    metrics = get_metrics_for_date(conn, user_id, today)
    return format_today_summary(meals, metrics)


def get_today_totals(conn: sqlite3.Connection, user_id: int) -> str:
    return get_today_meals_tool(conn, user_id)


def log_health_sync(conn: sqlite3.Connection, user_id: int, date: str,
                    steps: int | None = None, sleep_deep_mins: int | None = None,
                    sleep_total_mins: int | None = None, resting_hr: int | None = None) -> str:
    upsert_health_metrics(conn, user_id, date, steps, sleep_deep_mins, sleep_total_mins, resting_hr)
    result = f"Health metrics synced for {date}."

    # Trigger async insight regeneration — non-blocking
    try:
        from orchestrator.insights import trigger_insights_async
        trigger_insights_async(user_id, scope="today")
    except Exception:
        pass  # Never let insight trigger block the health sync response

    return result
