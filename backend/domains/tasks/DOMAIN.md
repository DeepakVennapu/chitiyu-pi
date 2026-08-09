# Tasks Domain

## Overview

Manages Deepak's to-do items across two parallel models:

- **One-off tasks** (`tasks` table) — manually created tasks with optional `due_at` and `priority`.
- **Recurring tasks** (`task_templates` + `task_instances`) — template-driven recurring work spawned on demand per date.

**Design rule:** only the orchestrator crosses domain lines. This file documents everything a future developer needs to maintain the tasks domain without reading any other domain.

---

## Data Model

### One-Off Tasks (`tasks`)

| Column | Type | Notes |
|--------|------|-------|
| `id` | INTEGER PK | Auto-increment |
| `user_id` | INTEGER | Default 1 (solo-user phase) |
| `title` | TEXT | Task description |
| `due_at` | TEXT | ISO datetime `YYYY-MM-DDTHH:MM:SS` in local time, nullable |
| `completed_at` | TEXT | Set when task is completed; NULL means pending |
| `priority` | INTEGER | 0=normal, 1=high, 2=urgent |
| `tags` | TEXT | JSON array string, default `'[]'` |
| `created_at` | TEXT | Local time, auto-set |

### Recurring Templates (`task_templates`)

| Column | Type | Notes |
|--------|------|-------|
| `id` | INTEGER PK | Auto-increment |
| `user_id` | INTEGER | Default 1 |
| `title` | TEXT | Task title repeated on each occurrence |
| `recurrence` | TEXT | `daily` \| `weekly` \| `monthly` \| `yearly` |
| `anchor_date` | TEXT | `YYYY-MM-DD` — first occurrence date; determines weekday/day-of-month for future matches |
| `advance_days` | INTEGER | How many days before the due date to surface the instance |
| `created_at` | TEXT | Auto-set |

### Recurring Instances (`task_instances`)

| Column | Type | Notes |
|--------|------|-------|
| `id` | INTEGER PK | Auto-increment |
| `template_id` | INTEGER FK | References `task_templates(id)` ON DELETE CASCADE |
| `user_id` | INTEGER | Default 1 |
| `due_date` | TEXT | `YYYY-MM-DD` — the specific date this instance covers |
| `completed_at` | TEXT | Nullable; set when completed |
| `deleted_at` | TEXT | Soft-delete; NULL means active |
| `created_at` | TEXT | Auto-set |

Unique constraint: `(template_id, due_date)` — one instance per template per date, enforced via `INSERT OR IGNORE`.

---

## Recurring Task Model

### How Templates Fire

`_template_fires_on(recurrence, anchor_date, target_date) → bool`

| Recurrence | Fires when |
|-----------|-----------|
| `daily` | Every date on or after `anchor_date` |
| `weekly` | Same weekday as `anchor_date` |
| `monthly` | Same day-of-month as `anchor_date` |
| `yearly` | Same month+day as `anchor_date` |

No firing before `anchor_date`.

### Advance Window

Instances are only spawned if `today >= anchor_date - advance_days`. This prevents surfacing future-only tasks too early.

**Default advance by recurrence** (set in router when `advance_days` is omitted):

| Recurrence | Default `advance_days` |
|-----------|----------------------|
| `daily` | 1 |
| `weekly` | 1 |
| `monthly` | 7 |
| `yearly` | 30 |

### Spawn-on-Read Pattern

Instances are **not** pre-created. `spawn_instances_for_date(conn, user_id, date_iso)` is called at read time in `/tasks/today` and `/tasks/by-date`. It:
1. Iterates all active templates.
2. Checks `_template_fires_on` for the requested date.
3. Checks the advance window.
4. `INSERT OR IGNORE` into `task_instances`.
5. Returns the live instance row if it exists and is not completed/deleted.

This means the same date endpoint is idempotent — calling it twice doesn't double-create instances.

### UID Scheme

Both task types are returned with a `uid` string to allow the frontend to address them without knowing the underlying table:

| Prefix | Example | Source |
|--------|---------|--------|
| `t:` | `t:42` | One-off task from `tasks` table |
| `i:` | `i:17` | Recurring instance from `task_instances` |

Complete and delete endpoints use this prefix to route to the correct DB function.

---

## Priority / Sort

All pending task queries use the same ordering: `ORDER BY priority DESC, due_at ASC NULLS LAST`

- Higher priority tasks surface first.
- Within the same priority tier, earlier due dates sort first.
- Tasks with no `due_at` sort to the bottom.

---

## Finance Milestone Confirmation Tasks

The finance domain seeds recurring templates to remind Deepak to confirm his Chase Checking balance on each paycheck day. These are standard `task_templates` with:

- `recurrence = 'biweekly'` (approximated as `weekly` with a bi-weekly anchor)
- Title pattern: `"Confirm Chase Checking balance — [period_label]"`
- Completing the task is the user's cue to call `PATCH /finance/milestones/{target_date}` with the actual balance.

**Important:** these tasks are seeded in the finance domain seed step, not via the tasks API. They live in `task_templates` and spawn instances on paycheck dates like any other template.

---

## NL Task Parsing

`create_tasks_from_input(conn, user_id, text) → list[dict]`

Sends the user's free-form text to Haiku (`DISPATCH_MODEL`) with a structured prompt. Returns a JSON array of task objects. The parser handles:
- Multi-item lists ("pick up milk, eggs, bread" → 3 tasks)
- Relative dates ("tomorrow", "next Monday", "in 3 days")
- Priority hints ("urgent", "ASAP", "critical" → priority 2; "important" → priority 1)
- Recurring tasks ("every Monday", "daily standup") → inserts a template instead of a one-off task

If Haiku returns unparseable JSON, falls back to creating a single task with the raw text as the title.

---

## Key DB Functions

### `insert_task(conn, user_id, title, due_at, priority) → int`
Inserts a one-off task. Returns the new row `id`.

### `get_pending_tasks(conn, user_id) → list`
All tasks where `completed_at IS NULL`, sorted by `priority DESC, due_at ASC NULLS LAST`.

### `get_overdue_tasks(conn, user_id) → list`
Pending tasks where `due_at < local_now().isoformat()`. Used by the 4pm midday nudge and orchestrator context injection.

### `get_today_tasks(conn, user_id) → list`
Pending tasks where `date(due_at) = today_local()`. Does NOT include recurring instances — callers must also call `spawn_instances_for_date`.

### `get_tasks_by_date(conn, user_id, date_iso) → list`
Like `get_today_tasks` but for any date.

### `get_dates_summary(conn, user_id, start_iso, end_iso) → dict[str, int]`
Returns `{"YYYY-MM-DD": max_priority}` for all dates in range that have pending tasks OR active template firings. Used by the calendar date-dot display in the app. Dates with only template firings (no spawned instances yet) are included with `priority=0`.

### `complete_task(conn, user_id, task_id) → bool`
Sets `completed_at` to UTC now. Returns `False` if not found or already complete.

### `delete_task(conn, user_id, task_id) → bool`
Hard deletes from `tasks`. Returns `False` if not found.

### `insert_template(conn, user_id, title, recurrence, anchor_date, advance_days) → int`
Inserts a recurring template. Returns the template `id`.

### `get_active_templates(conn, user_id) → list`
All templates for the user, ordered by `created_at ASC`.

### `spawn_instances_for_date(conn, user_id, date_iso) → list[dict]`
Spawn-on-read: inserts missing instances and returns pending (non-completed, non-deleted) ones for the date. Each returned dict includes `uid`, `template_id`, `is_recurring: True`.

### `complete_instance(conn, user_id, instance_id) → bool`
Sets `completed_at` on the instance row.

### `delete_instance(conn, user_id, instance_id) → bool`
Soft-deletes by setting `deleted_at` (preserves the row for history).

---

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/tasks/` | Create task(s) — NL text parsed by Haiku; may create a template if recurring |
| `GET` | `/tasks/` | All pending one-off tasks |
| `GET` | `/tasks/overdue` | Pending tasks past their `due_at` |
| `GET` | `/tasks/today` | Today's one-off tasks + spawned recurring instances |
| `GET` | `/tasks/by-date?date=YYYY-MM-DD` | Tasks + instances for any date |
| `GET` | `/tasks/dates-summary?start=&end=` | Date→max_priority map for calendar dot display |
| `POST` | `/tasks/templates` | Create a recurring template |
| `PATCH` | `/tasks/instances/{instance_id}/complete` | Complete a recurring instance |
| `DELETE` | `/tasks/instances/{instance_id}` | Soft-delete a recurring instance |
| `PATCH` | `/tasks/{task_id}/complete` | Complete a one-off task |
| `DELETE` | `/tasks/{task_id}` | Hard-delete a one-off task |

**Route ordering note:** instance routes (`/tasks/instances/...`) are registered before `/{task_id}` routes to prevent FastAPI routing `instances` as a task ID path parameter.

---

## Response Shapes

### One-off task (from `GET /tasks/` or `GET /tasks/today`)
```json
{
  "id": 42,
  "uid": "t:42",
  "user_id": 1,
  "title": "Call dentist",
  "due_at": "2026-08-10T09:00:00",
  "completed_at": null,
  "priority": 1,
  "tags": [],
  "created_at": "2026-08-09 08:00:00"
}
```

### Recurring instance (from `GET /tasks/today` or `GET /tasks/by-date`)
```json
{
  "id": 17,
  "uid": "i:17",
  "template_id": 3,
  "title": "Confirm Chase Checking balance",
  "due_date": "2026-08-14",
  "due_at": "2026-08-14T00:00:00",
  "completed_at": null,
  "priority": 0,
  "tags": [],
  "is_recurring": true
}
```

### `GET /tasks/dates-summary`
```json
{
  "2026-08-09": 2,
  "2026-08-10": 0,
  "2026-08-14": 0
}
```
Value is `max_priority` of pending tasks/instances for that date. `0` means a template fires but no high-priority tasks.

---

## Frontend Integration

`tasks.tsx` uses `uid` as the stable key for all operations — never the raw `id`. Complete and delete calls check the `uid` prefix:
- `uid.startsWith("i:")` → call instance endpoints
- `uid.startsWith("t:")` → call task endpoints

`GET /tasks/dates-summary` drives the calendar date-dot display: any date with a non-null entry gets a dot; dot color/size can vary by priority if desired.

The `POST /tasks/` endpoint creates via NL text through `create_tasks_from_input`. The router returns the first created task for backwards compatibility with `app/addTask()`.

---

## Orchestrator Context Injection

`TasksDomain.inject_context()` checks `get_overdue_tasks()` and prepends an overdue count + formatted list to the LLM system prompt when there are outstanding overdue tasks. This ensures the AI is aware of pending obligations when the user sends any message routed to the tasks domain.

The insights engine (`orchestrator/insights.py`) fetches `/tasks/today` and `/tasks/overdue` to include task state in cross-domain insight cards. The 4pm scheduler job (`_midday_nudge`) also calls `get_overdue_tasks` directly and sends a Telegram nudge if overdue tasks exist.

---

## Known Issues / Gaps

- **`biweekly` recurrence not supported** — `task_templates.recurrence` CHECK constraint only allows `none|daily|weekly|monthly|yearly`. Finance milestone confirmation tasks would ideally use `biweekly` but currently require manual setup or using `weekly` with care.
- **Advance window uses `date.today()`** — `spawn_instances_for_date` compares against `date.today()` (system date), not `today_local()`. For users in UTC-offset timezones, this is effectively the same but could diverge around midnight.
- **No template edit/delete API** — templates can be created but not updated or deleted via the API. Requires direct DB manipulation to remove a recurring series.
- **One-off task `completed_at` uses UTC** — unlike `logged_at` in health, `completed_at` is stamped with `datetime.now(timezone.utc).isoformat()`. Querying completion by local date requires offset awareness.
