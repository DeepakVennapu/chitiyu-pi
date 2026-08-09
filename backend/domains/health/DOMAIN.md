# Health Domain

## Timestamp Convention

All `logged_at` values are stored as `YYYY-MM-DD HH:MM:SS` in **system local time** (no timezone suffix). Do not store UTC.

**Why:** SQLite's `date(logged_at)` comparison uses the literal string value. If timestamps are stored in UTC but "today" is computed in local time, meals logged after ~6pm appear on the wrong day's dashboard.

**Insert path:** `insert_meal` always calls `_to_local_ts(logged_at)` on incoming values. The frontend sends UTC ISO strings (e.g. `2026-08-08T04:24:57.000Z`); `_to_local_ts` converts to local before storage. When no `logged_at` is provided, `_local_now()` supplies the current local time.

**Query path:** `get_today_meals` and `get_meals_for_date` compare `date(logged_at)` against a local date string from `_today_local()`. Both sides of the comparison are in local time.

**Display path (frontend):** `parseLocalTs()` in `app/lib/dateUtils.ts` treats bare DB strings as local — it does **not** append `Z`. Appending Z would shift display by the UTC offset (6h for MDT).

## "Today" Definition

`_today_local()` (from `utils.local_time`) returns the current date in system local time. All "today" endpoints use this — never `datetime.now(timezone.utc).date()`.

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health/meals/today` | Today's meals + metrics + summary |
| `GET` | `/health/summary/{date}` | Meals + metrics + summary for any date (`YYYY-MM-DD`) |
| `POST` | `/health/meals/log-parsed` | Log a meal with pre-parsed macros; accepts optional `logged_at` (UTC ISO) |
| `POST` | `/health/meals/preview` | Parse meal text into macros without logging |
| `POST` | `/health/meals` | Log meal via NL text (AI-parsed) |
| `GET` | `/health/recipes` | List saved recipes |
| `POST` | `/health/recipes` | Create a recipe |
| `POST` | `/health/meals/from-recipe` | Log a meal from a saved recipe |
| `DELETE` | `/health/meals/{id}` | Delete a meal |
| `POST` | `/health/sync` | Upsert health metrics (steps, sleep, HR) for a date |
| `GET` | `/health/metrics/today` | Today's health metrics |
| `GET` | `/health/metrics/{date}` | Health metrics for a specific date |
