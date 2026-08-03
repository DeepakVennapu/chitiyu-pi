import json, re, sqlite3
from orchestrator.llm import call_claude
from domains.health.db import insert_meal, get_today_meals, upsert_health_metrics
from domains.health.formatter import format_today_summary, format_meal_confirmation, TARGETS
from config import DISPATCH_MODEL

_PARSE_PROMPT = """\
Parse this meal description into macros. Return JSON only:
{{"description": "<clean name>", "calories": <int>, "protein": <float>, "fat": <float>, "carbs": <float>}}
Context (if any): {context}
Meal: {text}"""


def log_meal(conn: sqlite3.Connection, user_id: int, text: str, context: str = "") -> str:
    raw = call_claude(_PARSE_PROMPT.format(text=text, context=context),
                      model=DISPATCH_MODEL, timeout=20)
    m = re.search(r'\{.*\}', raw, re.DOTALL)
    if not m:
        return "Couldn't parse that meal. Try: '2 eggs, toast, coffee'."
    data = json.loads(m.group())
    insert_meal(conn, user_id, data["description"], data["calories"],
                data["protein"], data.get("fat"), data.get("carbs"))
    return format_meal_confirmation(data["description"], data["calories"], data["protein"])


def get_today_meals_tool(conn: sqlite3.Connection, user_id: int) -> str:
    from domains.health.db import get_today_meals as _get
    meals = _get(conn, user_id)
    metrics = None
    from datetime import datetime, timezone
    today = datetime.now(timezone.utc).date().isoformat()
    from domains.health.db import get_metrics_for_date
    metrics = get_metrics_for_date(conn, user_id, today)
    return format_today_summary(meals, metrics)


def get_today_totals(conn: sqlite3.Connection, user_id: int) -> str:
    return get_today_meals_tool(conn, user_id)


def log_health_sync(conn: sqlite3.Connection, user_id: int, date: str,
                    steps: int | None = None, sleep_deep_mins: int | None = None,
                    sleep_total_mins: int | None = None, resting_hr: int | None = None) -> str:
    upsert_health_metrics(conn, user_id, date, steps, sleep_deep_mins, sleep_total_mins, resting_hr)
    return f"Health metrics synced for {date}."
