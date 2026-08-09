# Smart Input FAB Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace literal-string logging across all domains with LLM-parsed intelligent input, and add a floating action button (FAB) that gives a single global entry point routing to a rich preview+confirm flow.

**Architecture:** Three layers — (1) Backend: smart task parser + `POST /chat` global endpoint that returns structured `ChatResponse` (prose + per-domain write previews); (2) Frontend: shared `SmartInputSheet` component with sequential domain preview/confirm/correct flow; (3) FAB wired into the tab layout, always hitting global, while per-tab Log buttons stay domain-specific but gain the same preview pattern.

**Tech Stack:** Python/FastAPI (backend), React Native / Expo Router / TypeScript (frontend), Claude Haiku 4.5 for parsing, Claude Sonnet 4.6 for global chat, existing `call_claude`, `insert_task`, `insert_template`, `parse_meal_macros` + `insert_meal`, `parse_transaction_input` + `insert_transaction`.

## Global Constraints

- Python backend: all new files under `backend/`, follow existing `conn`/`user_id` patterns
- No domain may import from another domain — all cross-domain work in `orchestrator/`
- Frontend: use `useTheme()` + `colors.*` tokens everywhere, no inline hex
- API auth: `X-API-Key` header on all new endpoints (use existing `verify_api_key` dependency)
- All new backend endpoints tested in `tests/` using the in-memory `conn` fixture from `conftest.py`
- `call_claude` is mocked in tests via `unittest.mock.patch("orchestrator.llm.call_claude")`
- Tasks: flat tasks only (no parent/child), recurring via `insert_template` + `spawn_instances_for_date`
- Priority inferred from urgency language: urgent/ASAP/critical → 2, high/important → 1, else 0
- Due dates: relative ("tomorrow", "next Monday") resolved against `today_local()` in the parser
- FAB `bottom` offset uses `useSafeAreaInsets()` — never hardcode pixel values
- Expo SDK 54 — check https://docs.expo.dev/versions/v54.0.0/ before writing component code

---

### Task 1: Smart task parser

**Files:**
- Modify: `backend/domains/tasks/tools.py`
- Test: `tests/test_tasks_tools.py` (create new)

**Interfaces:**
- Produces: `parse_task_input(text: str, today: str) -> list[dict]`
  - Each dict: `{"title": str, "due_at": str | None, "priority": int, "recurrence": str | None, "anchor_date": str | None}`
  - `recurrence` is one of `"daily"`, `"weekly"`, `"monthly"`, `"yearly"`, or `None`
  - `anchor_date` is `"YYYY-MM-DD"` — only present when `recurrence` is not None
  - `priority`: 0 (default), 1 (high/important), 2 (urgent/ASAP/critical)
  - `due_at`: ISO datetime string `"YYYY-MM-DDTHH:MM:SS"` or None
- Produces: `create_tasks_from_input(conn, user_id, text) -> list[dict]`
  - Returns list of created task dicts: `{"id": int, "title": str, "due_at": str | None, "priority": int, "is_recurring": bool}`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_tasks_tools.py
import sys, os, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))
import pytest
from unittest.mock import patch
from domains.tasks.tools import parse_task_input, create_tasks_from_input


def test_parse_single_task_no_date():
    payload = [{"title": "Call dentist", "due_at": None, "priority": 0, "recurrence": None, "anchor_date": None}]
    with patch("domains.tasks.tools.call_claude", return_value=json.dumps(payload)):
        result = parse_task_input("Call dentist", today="2026-08-08")
    assert len(result) == 1
    assert result[0]["title"] == "Call dentist"
    assert result[0]["due_at"] is None
    assert result[0]["priority"] == 0


def test_parse_multiple_subtasks():
    payload = [
        {"title": "Buy chicken", "due_at": "2026-08-09T00:00:00", "priority": 0, "recurrence": None, "anchor_date": None},
        {"title": "Buy coriander", "due_at": "2026-08-09T00:00:00", "priority": 0, "recurrence": None, "anchor_date": None},
        {"title": "Buy onions", "due_at": "2026-08-09T00:00:00", "priority": 0, "recurrence": None, "anchor_date": None},
    ]
    with patch("domains.tasks.tools.call_claude", return_value=json.dumps(payload)):
        result = parse_task_input("Buy groceries: chicken, coriander, onions tomorrow", today="2026-08-08")
    assert len(result) == 3
    assert result[0]["due_at"] == "2026-08-09T00:00:00"


def test_parse_urgency_priority():
    payload = [{"title": "Fix prod bug", "due_at": None, "priority": 2, "recurrence": None, "anchor_date": None}]
    with patch("domains.tasks.tools.call_claude", return_value=json.dumps(payload)):
        result = parse_task_input("URGENT: fix prod bug", today="2026-08-08")
    assert result[0]["priority"] == 2


def test_parse_recurring_weekly():
    payload = [{"title": "Call mom", "due_at": None, "priority": 0, "recurrence": "weekly", "anchor_date": "2026-08-11"}]
    with patch("domains.tasks.tools.call_claude", return_value=json.dumps(payload)):
        result = parse_task_input("Call mom every Monday", today="2026-08-08")
    assert result[0]["recurrence"] == "weekly"
    assert result[0]["anchor_date"] == "2026-08-11"


def test_create_tasks_from_input_one_off(conn, user_id):
    payload = [{"title": "Buy milk", "due_at": "2026-08-09T00:00:00", "priority": 0, "recurrence": None, "anchor_date": None}]
    with patch("domains.tasks.tools.call_claude", return_value=json.dumps(payload)):
        created = create_tasks_from_input(conn, user_id, "Buy milk tomorrow")
    assert len(created) == 1
    assert created[0]["title"] == "Buy milk"
    assert created[0]["is_recurring"] is False


def test_create_tasks_from_input_recurring(conn, user_id):
    payload = [{"title": "Call mom", "due_at": None, "priority": 0, "recurrence": "weekly", "anchor_date": "2026-08-11"}]
    with patch("domains.tasks.tools.call_claude", return_value=json.dumps(payload)):
        created = create_tasks_from_input(conn, user_id, "Call mom every Monday")
    assert len(created) == 1
    assert created[0]["is_recurring"] is True
```

- [ ] **Step 2: Run to verify failure**

```bash
cd ~/deep-workspace/chitiyu-pi && uv run pytest tests/test_tasks_tools.py -v
```
Expected: `ImportError` or `AttributeError` — `parse_task_input` does not exist yet.

- [ ] **Step 3: Implement `parse_task_input` and `create_tasks_from_input` in `tools.py`**

Add to `backend/domains/tasks/tools.py` (keep existing functions unchanged):

```python
import json, re
from utils.local_time import today_local
from orchestrator.llm import call_claude
from config import DISPATCH_MODEL

_PARSE_TASKS_PROMPT = """\
Parse the user's input into one or more tasks. Return a JSON array only — no explanation.

Today's date: {today}

Rules:
- If the input lists items (e.g. "groceries: chicken, onions"), create one task per item.
- Resolve relative dates ("tomorrow", "next Monday", "in 3 days") against today's date.
- due_at: ISO datetime string "YYYY-MM-DDTHH:MM:SS" or null if no date mentioned.
- priority: 2 if urgent/ASAP/critical, 1 if high/important, else 0.
- recurrence: "daily", "weekly", "monthly", "yearly", or null.
- anchor_date: "YYYY-MM-DD" for the first occurrence when recurrence is not null, else null.
- If recurring, due_at should be null.

Return format (array of objects):
[{{"title": "...", "due_at": "...|null", "priority": 0|1|2, "recurrence": "...|null", "anchor_date": "...|null"}}]

Input: {text}"""


def parse_task_input(text: str, today: str | None = None) -> list[dict]:
    """Parse NL task input into a list of structured task dicts via Haiku."""
    today = today or today_local()
    raw = call_claude(
        _PARSE_TASKS_PROMPT.format(today=today, text=text),
        model=DISPATCH_MODEL,
        timeout=20,
    )
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = "\n".join(cleaned.split("\n")[1:])
        if cleaned.endswith("```"):
            cleaned = cleaned[:cleaned.rfind("```")]
        cleaned = cleaned.strip()
    m = re.search(r'\[.*\]', cleaned, re.DOTALL)
    if not m:
        return [{"title": text.strip(), "due_at": None, "priority": 0, "recurrence": None, "anchor_date": None}]
    try:
        return json.loads(m.group())
    except json.JSONDecodeError:
        return [{"title": text.strip(), "due_at": None, "priority": 0, "recurrence": None, "anchor_date": None}]


def create_tasks_from_input(conn, user_id: int, text: str) -> list[dict]:
    """Parse NL text and insert all resulting tasks/templates. Returns created task dicts."""
    parsed = parse_task_input(text)
    created = []
    for item in parsed:
        if item.get("recurrence") and item.get("anchor_date"):
            tid = insert_template(
                conn, user_id,
                title=item["title"],
                recurrence=item["recurrence"],
                anchor_date=item["anchor_date"],
                advance_days=1,
            )
            created.append({
                "id": tid,
                "title": item["title"],
                "due_at": None,
                "priority": item.get("priority", 0),
                "is_recurring": True,
            })
        else:
            task_id = insert_task(
                conn, user_id,
                title=item["title"],
                due_at=item.get("due_at"),
                priority=item.get("priority", 0),
            )
            created.append({
                "id": task_id,
                "title": item["title"],
                "due_at": item.get("due_at"),
                "priority": item.get("priority", 0),
                "is_recurring": False,
            })
    return created
```

Also update the import at the top of the existing file:
```python
from domains.tasks.db import insert_task, get_pending_tasks, complete_task, insert_template
```
(replace the existing line that only imports `insert_task, get_pending_tasks, complete_task`)

- [ ] **Step 4: Run tests to verify pass**

```bash
cd ~/deep-workspace/chitiyu-pi && uv run pytest tests/test_tasks_tools.py -v
```
Expected: all 6 tests PASS.

- [ ] **Step 5: Update tasks router to use `create_tasks_from_input`**

In `backend/domains/tasks/router.py`, find the `POST /tasks/` endpoint and update it:

```python
# Find this class:
class TaskCreate(BaseModel):
    user_id: int = 1
    title: str
    due_at: str | None = None
    priority: int = 0
    tags: list[str] = []

# Find the POST /tasks/ handler and replace its body:
@router.post("/")
def create_task_endpoint(body: TaskCreate):
    from domains.tasks.tools import create_tasks_from_input
    conn = _conn()
    created = create_tasks_from_input(conn, body.user_id, body.title)
    conn.close()
    # Return first created task shape for backwards compat with app's addTask() call
    if not created:
        raise HTTPException(422, "Could not parse task input")
    first = created[0]
    return {**first, "uid": f"t:{first['id']}", "tags": [], "completed_at": None}
```

- [ ] **Step 6: Run full test suite to check for regressions**

```bash
cd ~/deep-workspace/chitiyu-pi && uv run pytest -v
```
Expected: all previously passing tests still pass.

- [ ] **Step 7: Commit**

```bash
git add backend/domains/tasks/tools.py backend/domains/tasks/router.py tests/test_tasks_tools.py
git commit -m "feat(tasks): smart NL parser — subtasks, due dates, priority, recurrence"
```

---

### Task 2: Rename `_parse_transaction_text` → `parse_transaction_input`

The function `_parse_transaction_text` in `backend/domains/finance/tools.py` is used by `orchestrator/chat.py` in Task 3. The leading underscore signals a private helper — rename it to a proper public interface before wiring it into the orchestrator.

**Files:**
- Modify: `backend/domains/finance/tools.py`

- [ ] **Step 1: Rename the function and update all internal callers**

In `backend/domains/finance/tools.py`:

1. Rename `_parse_transaction_text` to `parse_transaction_input` (remove leading underscore).
2. Update the two internal callers in the same file (`add_transaction` and `add_transaction_structured`) to call `parse_transaction_input(...)` instead of `_parse_transaction_text(...)`.

- [ ] **Step 2: Run the full test suite**

```bash
cd ~/deep-workspace/chitiyu-pi && uv run pytest -v
```
Expected: all tests pass — no references to `_parse_transaction_text` remain.

- [ ] **Step 3: Commit**

```bash
git add backend/domains/finance/tools.py
git commit -m "refactor(finance): rename _parse_transaction_text to parse_transaction_input"
```

---

### Task 3: `POST /chat` global endpoint

**Files:**
- Create: `backend/orchestrator/chat.py`
- Create: `backend/orchestrator/chat_router.py`
- Modify: `backend/main.py`
- Test: `tests/test_chat.py` (create new)

**Interfaces:**
- Consumes (Task 1): `parse_task_input(text, today)` from `domains/tasks/tools.py`
- Consumes (Task 2): `parse_transaction_input(text, context)` from `domains/finance/tools.py`
- Consumes (existing): `parse_meal_macros(text, context)` from `domains/health/tools.py`
- Produces: `POST /chat` → `ChatResponse`

```python
# ChatResponse shape (returned as JSON):
{
  "prose": str,                  # conversational answer or "" if pure write
  "domains": [                   # zero or more write previews
    {
      "domain": "health" | "finance" | "tasks",
      "preview": {               # domain-specific — see below
        # health:   {"description": str, "calories": int, "protein": float, "fat": float|null, "carbs": float|null}
        # finance:  {"description": str, "amount": float, "category": str, "date": str}
        # tasks:    [{"title": str, "due_at": str|null, "priority": int, "is_recurring": bool}]
      },
      "extract": str,            # domain-relevant fragment for correction pre-fill
    }
  ],
  "actions": [
    {"label": str, "domain": "tasks", "prefill": str}
  ]
}
```

- Produces: `POST /chat/confirm` → `{"ok": True, "result": str}`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_chat.py
import sys, os, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))
import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient


@pytest.fixture
def client(conn):
    import main
    with patch("orchestrator.chat_router._conn", return_value=conn):
        yield TestClient(main.app)


# ── Router-level tests (mock build_chat_response) ────────────────────────────

def test_chat_pure_query(client):
    """A question with no loggable data returns prose only, no domain previews."""
    with patch("orchestrator.chat.build_chat_response") as mock_build:
        mock_build.return_value = {
            "prose": "You have $460 discretionary left.",
            "domains": [],
            "actions": [{"label": "Log as task", "domain": "tasks", "prefill": "Check budget"}],
        }
        resp = client.post("/chat", json={"text": "Do I have budget for a watch?"},
                           headers={"X-API-Key": "test"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["prose"] != ""
    assert data["domains"] == []


def test_chat_meal_only(client):
    with patch("orchestrator.chat.build_chat_response") as mock_build:
        mock_build.return_value = {
            "prose": "",
            "domains": [{"domain": "health", "preview": {"description": "chicken mozzarella", "calories": 680, "protein": 45.0, "fat": 22.0, "carbs": 30.0}, "extract": "chicken mozzarella"}],
            "actions": [],
        }
        resp = client.post("/chat", json={"text": "I had chicken mozzarella"},
                           headers={"X-API-Key": "test"})
    assert resp.status_code == 200
    assert resp.json()["domains"][0]["domain"] == "health"


def test_chat_multi_domain(client):
    with patch("orchestrator.chat.build_chat_response") as mock_build:
        mock_build.return_value = {
            "prose": "",
            "domains": [
                {"domain": "health", "preview": {"description": "chicken mozzarella", "calories": 680, "protein": 45.0, "fat": 22.0, "carbs": 30.0}, "extract": "chicken mozzarella"},
                {"domain": "finance", "preview": {"description": "Cheesecake Factory", "amount": -50.0, "category": "dining", "date": "2026-08-08"}, "extract": "$50 at Cheesecake Factory"},
            ],
            "actions": [],
        }
        resp = client.post("/chat", json={"text": "I had chicken mozzarella at Cheesecake Factory, spent $50"},
                           headers={"X-API-Key": "test"})
    assert resp.status_code == 200
    assert {d["domain"] for d in resp.json()["domains"]} == {"health", "finance"}


# ── Engine-level test (mock call_claude — verifies intent parsing) ────────────

def test_build_chat_response_meal(conn):
    """Verify build_chat_response correctly parses intent JSON and calls health parser."""
    from orchestrator.chat import build_chat_response
    intent_json = json.dumps({
        "prose": "",
        "health_extract": "chicken mozzarella",
        "finance_extract": None,
        "tasks_extract": None,
        "actions": [],
    })
    macro_json = json.dumps({"description": "chicken mozzarella", "calories": 680, "protein": 45.0, "fat": 22.0, "carbs": 30.0})
    with patch("orchestrator.chat.call_claude", side_effect=[intent_json, macro_json]):
        result = build_chat_response(conn, 1, "I had chicken mozzarella")
    assert len(result["domains"]) == 1
    assert result["domains"][0]["domain"] == "health"
    assert result["domains"][0]["preview"]["calories"] == 680


def test_build_chat_response_finance(conn):
    """Verify build_chat_response correctly parses finance intent and calls finance parser."""
    from orchestrator.chat import build_chat_response
    intent_json = json.dumps({
        "prose": "",
        "health_extract": None,
        "finance_extract": "$50 at Cheesecake Factory",
        "tasks_extract": None,
        "actions": [],
    })
    txn_json = json.dumps({"description": "Cheesecake Factory", "amount": -50.0, "category": "dining", "date": "2026-08-08"})
    with patch("orchestrator.chat.call_claude", side_effect=[intent_json, txn_json]):
        result = build_chat_response(conn, 1, "Spent $50 at Cheesecake Factory")
    assert len(result["domains"]) == 1
    assert result["domains"][0]["domain"] == "finance"
    assert result["domains"][0]["preview"]["amount"] == -50.0


# ── Confirm-endpoint tests ────────────────────────────────────────────────────

def test_chat_confirm_health(client, conn):
    from domains.health.db import get_today_meals
    with patch("orchestrator.chat_router._conn", return_value=conn):
        resp = client.post("/chat/confirm", json={
            "domain": "health",
            "preview": {"description": "eggs", "calories": 150, "protein": 12.0, "fat": 10.0, "carbs": 1.0},
            "user_id": 1,
        }, headers={"X-API-Key": "test"})
    assert resp.status_code == 200
    assert resp.json()["ok"] is True
    meals = get_today_meals(conn, 1)
    assert len(meals) == 1
    assert meals[0]["description"] == "eggs"


def test_chat_confirm_tasks(client, conn):
    from domains.tasks.db import get_pending_tasks
    with patch("orchestrator.chat_router._conn", return_value=conn):
        resp = client.post("/chat/confirm", json={
            "domain": "tasks",
            "preview": [
                {"title": "Buy chicken", "due_at": "2026-08-09T00:00:00", "priority": 0, "is_recurring": False},
                {"title": "Buy onions", "due_at": "2026-08-09T00:00:00", "priority": 0, "is_recurring": False},
            ],
            "user_id": 1,
        }, headers={"X-API-Key": "test"})
    assert resp.status_code == 200
    assert len(get_pending_tasks(conn, 1)) == 2


def test_chat_confirm_finance(client, conn):
    from domains.finance.db import list_transactions
    with patch("orchestrator.chat_router._conn", return_value=conn):
        resp = client.post("/chat/confirm", json={
            "domain": "finance",
            "preview": {"description": "Cheesecake Factory", "amount": -50.0, "category": "dining", "date": "2026-08-08"},
            "user_id": 1,
        }, headers={"X-API-Key": "test"})
    assert resp.status_code == 200
    txns = list_transactions(conn, 1)
    assert len(txns) == 1
    assert txns[0]["description"] == "Cheesecake Factory"
```

- [ ] **Step 2: Run to verify failure**

```bash
cd ~/deep-workspace/chitiyu-pi && uv run pytest tests/test_chat.py -v
```
Expected: `ImportError` — modules don't exist yet.

- [ ] **Step 3: Create `backend/orchestrator/chat.py`**

```python
# backend/orchestrator/chat.py
"""
Global chat engine — parses multi-domain intent from a single message.

build_chat_response() is the main entry point. It:
1. Calls Haiku once to detect which domains have loggable data and extract any prose answer
2. For each detected domain, calls the domain-specific parser to build a preview
3. Returns ChatResponse dict: prose + domain previews + suggested task actions
"""
from __future__ import annotations

import json
import logging
import re
import sqlite3
from typing import Any

from config import DISPATCH_MODEL
from orchestrator.llm import call_claude
from utils.local_time import today_local

logger = logging.getLogger(__name__)

_INTENT_SYSTEM = """\
You are a personal intelligence assistant. Analyze the user's message and determine:
1. Which domains have loggable data (health=meal/nutrition, finance=expense/income, tasks=task/reminder)
2. A prose response if the message is a question or needs an answer
3. Suggested "log as task" actions for recommendations you make

Return JSON only:
{{
  "prose": "<conversational answer or empty string>",
  "health_extract": "<meal description fragment or null>",
  "finance_extract": "<expense description fragment or null>",
  "tasks_extract": "<task description fragment or null>",
  "actions": [
    {{"label": "<button label>", "domain": "tasks", "prefill": "<pre-fill text>"}}
  ]
}}

Today: {today}

Rules:
- health_extract: only if the message describes eating/drinking something
- finance_extract: only if the message describes spending money or income
- tasks_extract: only if the message describes a task, reminder, or to-do
- prose: always answer questions; for pure logs with no question, use empty string
- actions: only when you make a recommendation that could become a task
- For knowledge graph queries (who is X, what does X like), answer in prose using provided context"""


def _extract_json(raw: str) -> dict:
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = "\n".join(cleaned.split("\n")[1:])
        if cleaned.endswith("```"):
            cleaned = cleaned[:cleaned.rfind("```")]
        cleaned = cleaned.strip()
    m = re.search(r'\{.*\}', cleaned, re.DOTALL)
    if not m:
        return {}
    try:
        return json.loads(m.group())
    except json.JSONDecodeError:
        return {}


def build_chat_response(
    conn: sqlite3.Connection,
    user_id: int,
    text: str,
    knowledge_context: str = "",
) -> dict[str, Any]:
    """
    Parse a free-text message. Returns:
    {"prose": str, "domains": [{"domain", "preview", "extract"}], "actions": [...]}
    """
    today = today_local()
    context_block = f"Context from memory:\n{knowledge_context}\n\n" if knowledge_context else ""
    intent_prompt = f"{context_block}User message: {text}"

    raw = call_claude(
        intent_prompt,
        system_prompt=_INTENT_SYSTEM.format(today=today),
        model=DISPATCH_MODEL,
        timeout=30,
    )
    intent = _extract_json(raw)

    domains: list[dict] = []

    health_extract = intent.get("health_extract")
    if health_extract:
        try:
            from domains.health.tools import parse_meal_macros
            preview = parse_meal_macros(health_extract)
            if preview:
                domains.append({"domain": "health", "preview": preview, "extract": health_extract})
        except Exception as exc:
            logger.warning("chat: health parse failed: %s", exc)

    finance_extract = intent.get("finance_extract")
    if finance_extract:
        try:
            from domains.finance.tools import parse_transaction_input
            preview = parse_transaction_input(finance_extract)
            if preview:
                domains.append({"domain": "finance", "preview": preview, "extract": finance_extract})
        except Exception as exc:
            logger.warning("chat: finance parse failed: %s", exc)

    tasks_extract = intent.get("tasks_extract")
    if tasks_extract:
        try:
            from domains.tasks.tools import parse_task_input
            parsed_tasks = parse_task_input(tasks_extract, today=today)
            if parsed_tasks:
                domains.append({"domain": "tasks", "preview": parsed_tasks, "extract": tasks_extract})
        except Exception as exc:
            logger.warning("chat: tasks parse failed: %s", exc)

    return {
        "prose": intent.get("prose", ""),
        "domains": domains,
        "actions": intent.get("actions", []),
    }
```

- [ ] **Step 4: Create `backend/orchestrator/chat_router.py`**

```python
# backend/orchestrator/chat_router.py
from __future__ import annotations

import sqlite3
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from auth import verify_api_key
from config import DB_PATH
from db.connection import get_connection
from db.schema import initialize_schema
from orchestrator.chat import build_chat_response

router = APIRouter(prefix="/chat", tags=["chat"],
                   dependencies=[Depends(verify_api_key)])


def _conn() -> sqlite3.Connection:
    c = get_connection(DB_PATH)
    initialize_schema(c)
    return c


class ChatRequest(BaseModel):
    text: str
    user_id: int = 1


class ConfirmRequest(BaseModel):
    domain: str   # "health" | "finance" | "tasks"
    preview: Any  # dict for health/finance, list[dict] for tasks
    user_id: int = 1


@router.post("")
def chat(body: ChatRequest):
    conn = _conn()
    try:
        knowledge_context = ""
        try:
            from orchestrator.embedder import embed
            from domains.knowledge.search import semantic_search
            emb = embed(body.text)
            facts = semantic_search(conn, emb, body.user_id, top_n=5)
            if facts:
                knowledge_context = "\n".join(f"• {f['content']}" for f in facts)
        except Exception:
            pass
        return build_chat_response(conn, body.user_id, body.text, knowledge_context)
    finally:
        conn.close()


@router.post("/confirm")
def confirm(body: ConfirmRequest):
    conn = _conn()
    try:
        if body.domain == "health":
            p = body.preview
            from domains.health.db import insert_meal
            from domains.health.formatter import format_meal_confirmation
            insert_meal(conn, body.user_id, p["description"], p["calories"],
                        p["protein"], p.get("fat"), p.get("carbs"))
            result = format_meal_confirmation(p["description"], p["calories"], p["protein"])
            try:
                from orchestrator.insights import trigger_insights_async
                trigger_insights_async(body.user_id, scope="today")
            except Exception:
                pass
            return {"ok": True, "result": result}

        elif body.domain == "finance":
            p = body.preview
            from domains.finance.db import insert_transaction
            from domains.finance.tools import _fire_budget_event
            insert_transaction(conn, body.user_id, p["date"], float(p["amount"]),
                               p["category"], p["description"], source="manual")
            _fire_budget_event(conn, body.user_id, p["category"], float(p["amount"]))
            try:
                from orchestrator.insights import trigger_insights_async
                trigger_insights_async(body.user_id, scope="today")
            except Exception:
                pass
            return {"ok": True, "result": f"Logged {p['description']} — ${abs(p['amount']):.2f} [{p['category']}]"}

        elif body.domain == "tasks":
            from domains.tasks.db import insert_task, insert_template
            results = []
            for item in body.preview:
                if item.get("is_recurring") and item.get("anchor_date"):
                    insert_template(conn, body.user_id, title=item["title"],
                                    recurrence=item["recurrence"], anchor_date=item["anchor_date"],
                                    advance_days=1)
                else:
                    insert_task(conn, body.user_id, title=item["title"],
                                due_at=item.get("due_at"), priority=item.get("priority", 0))
                results.append(item["title"])
            conn.commit()
            return {"ok": True, "result": f"Created {len(results)} task(s): {', '.join(results)}"}

        else:
            raise HTTPException(400, f"Unknown domain: {body.domain!r}")
    finally:
        conn.close()
```

- [ ] **Step 5: Wire router into `main.py`**

In `backend/main.py`, add after the existing imports:
```python
from orchestrator.chat_router import router as chat_router
```
And add after `app.include_router(insights_router)`:
```python
app.include_router(chat_router)
```

- [ ] **Step 6: Run tests**

```bash
cd ~/deep-workspace/chitiyu-pi && uv run pytest tests/test_chat.py -v
```
Expected: all 8 tests PASS.

- [ ] **Step 7: Run full suite**

```bash
cd ~/deep-workspace/chitiyu-pi && uv run pytest -v
```
Expected: all previously passing tests still pass.

- [ ] **Step 8: Commit**

```bash
git add backend/orchestrator/chat.py backend/orchestrator/chat_router.py backend/main.py tests/test_chat.py
git commit -m "feat(orchestrator): POST /chat + /chat/confirm — multi-domain preview endpoint"
```

---

### Task 4: `POST /finance/transactions/preview` (Finance fast-path)

Finance needs its own preview endpoint so the Finance tab Log button can hit a domain-specific path (like Health's `/health/meals/preview`) rather than silently falling back to `/chat`.

**Files:**
- Modify: `backend/domains/finance/router.py`
- Test: `tests/test_finance_tools.py` (add one test)

**Interfaces:**
- Produces: `POST /finance/transactions/preview` → `FinancePreview`
  ```json
  {"description": str, "amount": float, "category": str, "date": str}
  ```
  Returns 422 if text cannot be parsed. Does NOT insert anything.

- [ ] **Step 1: Add preview test to existing `tests/test_finance_tools.py`**

Open `tests/test_finance_tools.py` and add at the end:

```python
def test_parse_transaction_input_basic():
    import json
    from domains.finance.tools import parse_transaction_input
    mock_response = json.dumps({
        "date": "2026-08-08", "amount": -50.0,
        "category": "dining", "description": "Cheesecake Factory"
    })
    with patch("domains.finance.tools.call_claude", return_value=mock_response):
        result = parse_transaction_input("$50 at Cheesecake Factory", context="")
    assert result["amount"] == -50.0
    assert result["category"] == "dining"
    assert result["description"] == "Cheesecake Factory"
```

(Add `from unittest.mock import patch` at the top of that file if not already present.)

- [ ] **Step 2: Run to verify the new test passes**

```bash
cd ~/deep-workspace/chitiyu-pi && uv run pytest tests/test_finance_tools.py -v
```
Expected: new test PASS (function was renamed in Task 2, not changed in behaviour).

- [ ] **Step 3: Add preview endpoint to `backend/domains/finance/router.py`**

Add after the existing imports (before `router = APIRouter(...)`):

```python
class TransactionPreview(BaseModel):
    user_id: int = 1
    text: str
    context: str = ""
```

Add the endpoint after the existing `POST /finance/transactions` endpoint:

```python
@router.post("/transactions/preview")
def preview_transaction(body: TransactionPreview):
    """Parse NL expense text and return structured preview — no insert."""
    from domains.finance.tools import parse_transaction_input
    result = parse_transaction_input(body.text, body.context)
    if result is None:
        raise HTTPException(422, "Couldn't parse that expense. Try: 'spent $45 at Whole Foods on groceries'.")
    return result
```

- [ ] **Step 4: Run full suite**

```bash
cd ~/deep-workspace/chitiyu-pi && uv run pytest -v
```
Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add backend/domains/finance/router.py tests/test_finance_tools.py
git commit -m "feat(finance): POST /finance/transactions/preview — dry-run parse without insert"
```

---

### Task 5: `api.ts` additions for chat

**Files:**
- Modify: `app/lib/api.ts`

**Interfaces:**
- Produces:
  - `chatMessage(text: string): Promise<ChatResponse>`
  - `confirmDomain(domain: DomainName, preview: DomainPreview, user_id?: number): Promise<ConfirmResult>`
  - `previewDomain(domain: DomainName, text: string): Promise<DomainBlock>`
  - Types: `ChatResponse`, `DomainBlock`, `DomainPreview`, `ChatAction`, `ConfirmResult`, `HealthPreview`, `FinancePreview`, `TaskPreviewItem`

- [ ] **Step 1: Add types and functions to `app/lib/api.ts`**

Add at the end of the file:

```typescript
// ─── Chat (Global Input) ──────────────────────────────────────────────────────

export type DomainName = "health" | "finance" | "tasks";

export interface HealthPreview {
  description: string;
  calories: number;
  protein: number;
  fat: number | null;
  carbs: number | null;
}

export interface FinancePreview {
  description: string;
  amount: number;
  category: string;
  date: string;
}

export interface TaskPreviewItem {
  title: string;
  due_at: string | null;
  priority: number;
  is_recurring: boolean;
  recurrence?: string;
  anchor_date?: string;
}

export type DomainPreview = HealthPreview | FinancePreview | TaskPreviewItem[];

export interface DomainBlock {
  domain: DomainName;
  preview: DomainPreview;
  extract: string;   // domain-relevant fragment — use for correction pre-fill
}

export interface ChatAction {
  label: string;
  domain: DomainName;
  prefill: string;
}

export interface ChatResponse {
  prose: string;
  domains: DomainBlock[];
  actions: ChatAction[];
}

export interface ConfirmResult {
  ok: boolean;
  result: string;
}

export const chatMessage = (text: string) =>
  request<ChatResponse>("POST", "/chat", { text });

export const confirmDomain = (domain: DomainName, preview: DomainPreview, user_id = 1) =>
  request<ConfirmResult>("POST", "/chat/confirm", { domain, preview, user_id });

// previewDomain — calls domain-specific preview endpoints directly (fast path).
// Health uses /health/meals/preview; Finance uses /finance/transactions/preview;
// Tasks falls back to /chat since there is no standalone task preview endpoint.
export const previewDomain = async (domain: DomainName, text: string): Promise<DomainBlock> => {
  if (domain === "health") {
    const data = await request<MealPreviewResult>("POST", "/health/meals/preview", { text });
    return { domain: "health", preview: data, extract: text };
  }
  if (domain === "finance") {
    const data = await request<FinancePreview>("POST", "/finance/transactions/preview", { text });
    return { domain: "finance", preview: data, extract: text };
  }
  // tasks: no standalone preview endpoint — route through global /chat
  const response = await chatMessage(text);
  const block = response.domains.find(d => d.domain === "tasks");
  if (!block) throw new Error("No tasks found in: " + text);
  return block;
};
```

- [ ] **Step 2: Verify TypeScript compiles**

```bash
cd ~/deep-workspace/chitiyu-pi/app && npx tsc --noEmit
```
Expected: no errors.

- [ ] **Step 3: Commit**

```bash
git add app/lib/api.ts
git commit -m "feat(app/api): ChatResponse types, chatMessage, confirmDomain, previewDomain"
```

---

### Task 6: `SmartInputSheet` component

**Files:**
- Create: `app/components/SmartInputSheet.tsx`

Reusable bottom sheet for global FAB and per-tab Log buttons. Handles the full parse → preview → confirm/correct loop.

**Props:**
```typescript
interface SmartInputSheetProps {
  visible: boolean;
  onClose: () => void;
  onConfirmed: () => void;   // called after ALL domains confirmed — caller triggers data refresh
  domainLock?: DomainName;   // if set, titles the sheet and uses previewDomain (fastPath)
  initialText?: string;
}
```

**State machine:** `idle → loading → preview(domainIndex) → confirming → correcting → done`

**Key behaviours (all from review):**
- Submit button label: **"Send"** (not "Parse & Preview")
- Prose-only response: show prose + "Done" button that calls `onClose()` without `onConfirmed()`
- Correction re-parse: calls `previewDomain(block.domain, correctedText)` — not global `/chat`
- "Log all" button appears when `domains.length > 1` — fires all confirms in parallel via `Promise.all`
- Success flash duration: **1500ms** before auto-close
- Correction text box pre-filled with `block.extract` (domain-relevant fragment only)

- [ ] **Step 1: Create `app/components/SmartInputSheet.tsx`**

```typescript
import React, { useState, useRef } from "react";
import {
  Modal, View, Text, TextInput, TouchableOpacity, ScrollView,
  ActivityIndicator, KeyboardAvoidingView, Platform, StyleSheet,
} from "react-native";
import { useTheme } from "../lib/theme";
import {
  chatMessage, confirmDomain, previewDomain,
  type ChatResponse, type DomainBlock, type DomainName, type DomainPreview,
  type HealthPreview, type FinancePreview, type TaskPreviewItem,
} from "../lib/api";

interface SmartInputSheetProps {
  visible: boolean;
  onClose: () => void;
  onConfirmed: () => void;
  domainLock?: DomainName;
  initialText?: string;
}

type Phase =
  | { type: "idle" }
  | { type: "loading" }
  | { type: "error"; message: string }
  | { type: "preview"; response: ChatResponse; domainIndex: number }
  | { type: "confirming"; response: ChatResponse; domainIndex: number }
  | { type: "correcting"; domainIndex: number; prefill: string; response: ChatResponse }
  | { type: "done" };

// ── Sub-cards ────────────────────────────────────────────────────────────────

function HealthPreviewCard({ preview, colors }: { preview: HealthPreview; colors: any }) {
  return (
    <View>
      <Text style={{ color: colors.text, fontWeight: "600", marginBottom: 4 }}>{preview.description}</Text>
      <Text style={{ color: colors.textSecondary }}>{preview.calories} kcal · {preview.protein}g protein</Text>
      {preview.fat != null && (
        <Text style={{ color: colors.textSecondary }}>{preview.fat}g fat · {preview.carbs}g carbs</Text>
      )}
    </View>
  );
}

function FinancePreviewCard({ preview, colors }: { preview: FinancePreview; colors: any }) {
  const sign = preview.amount < 0 ? "-" : "+";
  return (
    <View>
      <Text style={{ color: colors.text, fontWeight: "600", marginBottom: 4 }}>{preview.description}</Text>
      <Text style={{ color: colors.textSecondary }}>
        {sign}${Math.abs(preview.amount).toFixed(2)} · {preview.category} · {preview.date}
      </Text>
    </View>
  );
}

function TasksPreviewCard({ preview, colors }: { preview: TaskPreviewItem[]; colors: any }) {
  return (
    <View>
      {preview.map((t, i) => (
        <Text key={i} style={{ color: colors.text, marginBottom: 2 }}>
          {"• "}{t.title}
          {t.due_at ? ` — ${t.due_at.slice(0, 10)}` : ""}
          {t.priority > 0 ? ` [P${t.priority}]` : ""}
          {t.is_recurring ? " 🔁" : ""}
        </Text>
      ))}
    </View>
  );
}

function DomainPreviewCard({
  block, onYes, onNo, confirming, colors,
}: {
  block: DomainBlock; onYes: () => void; onNo: () => void; confirming: boolean; colors: any;
}) {
  const label = block.domain === "health" ? "🍽 Health"
    : block.domain === "finance" ? "💰 Finance" : "✅ Tasks";
  return (
    <View style={{ backgroundColor: colors.card, borderRadius: 12, padding: 16, marginBottom: 12 }}>
      <Text style={{ color: colors.textSecondary, fontSize: 12, marginBottom: 8 }}>{label}</Text>
      {block.domain === "health" && <HealthPreviewCard preview={block.preview as HealthPreview} colors={colors} />}
      {block.domain === "finance" && <FinancePreviewCard preview={block.preview as FinancePreview} colors={colors} />}
      {block.domain === "tasks" && <TasksPreviewCard preview={block.preview as TaskPreviewItem[]} colors={colors} />}
      <View style={{ flexDirection: "row", gap: 12, marginTop: 16 }}>
        {confirming ? (
          <ActivityIndicator color={colors.accent} />
        ) : (
          <>
            <TouchableOpacity
              style={{ flex: 1, backgroundColor: colors.accent, borderRadius: 8, padding: 12, alignItems: "center" }}
              onPress={onYes}
            >
              <Text style={{ color: "#fff", fontWeight: "600" }}>Yes, log it</Text>
            </TouchableOpacity>
            <TouchableOpacity
              style={{ flex: 1, backgroundColor: colors.cardElevated, borderRadius: 8, padding: 12, alignItems: "center" }}
              onPress={onNo}
            >
              <Text style={{ color: colors.text, fontWeight: "600" }}>No, correct</Text>
            </TouchableOpacity>
          </>
        )}
      </View>
    </View>
  );
}

// ── Main component ────────────────────────────────────────────────────────────

export function SmartInputSheet({
  visible, onClose, onConfirmed, domainLock, initialText,
}: SmartInputSheetProps) {
  const { colors } = useTheme();
  const [text, setText] = useState(initialText ?? "");
  const [phase, setPhase] = useState<Phase>({ type: "idle" });
  const correctionRef = useRef("");

  const reset = () => { setText(initialText ?? ""); setPhase({ type: "idle" }); };
  const handleClose = () => { reset(); onClose(); };

  // ── Send ──────────────────────────────────────────────────────────────────
  const handleSend = async (inputText: string) => {
    if (!inputText.trim()) return;
    setPhase({ type: "loading" });
    try {
      let response: ChatResponse;
      if (domainLock) {
        // Fast path: call domain-specific preview endpoint
        const block = await previewDomain(domainLock, inputText.trim());
        response = { prose: "", domains: [block], actions: [] };
      } else {
        response = await chatMessage(inputText.trim());
      }
      if (response.domains.length === 0 && !response.prose) {
        setPhase({ type: "error", message: "Nothing to log. Try again." });
        return;
      }
      setPhase({ type: "preview", response, domainIndex: 0 });
    } catch (e) {
      setPhase({ type: "error", message: e instanceof Error ? e.message : "Failed" });
    }
  };

  // ── Confirm one domain ────────────────────────────────────────────────────
  const handleYes = async (response: ChatResponse, domainIndex: number) => {
    const block = response.domains[domainIndex];
    setPhase({ type: "confirming", response, domainIndex });
    try {
      await confirmDomain(block.domain, block.preview);
      const next = domainIndex + 1;
      if (next < response.domains.length) {
        setPhase({ type: "preview", response, domainIndex: next });
      } else {
        setPhase({ type: "done" });
        onConfirmed();
        setTimeout(() => { reset(); onClose(); }, 1500);
      }
    } catch (e) {
      setPhase({ type: "error", message: e instanceof Error ? e.message : "Confirm failed" });
    }
  };

  // ── Log all domains at once ───────────────────────────────────────────────
  const handleLogAll = async (response: ChatResponse) => {
    setPhase({ type: "loading" });
    try {
      await Promise.all(
        response.domains.map(block => confirmDomain(block.domain, block.preview))
      );
      setPhase({ type: "done" });
      onConfirmed();
      setTimeout(() => { reset(); onClose(); }, 1500);
    } catch (e) {
      setPhase({ type: "error", message: e instanceof Error ? e.message : "Bulk confirm failed" });
    }
  };

  // ── Decline → correct ─────────────────────────────────────────────────────
  const handleNo = (response: ChatResponse, domainIndex: number) => {
    const block = response.domains[domainIndex];
    correctionRef.current = block.extract;
    setPhase({ type: "correcting", domainIndex, prefill: block.extract, response });
  };

  // ── Re-parse just the corrected domain ───────────────────────────────────
  const handleCorrectionSend = async (
    correctedText: string, response: ChatResponse, domainIndex: number
  ) => {
    const block = response.domains[domainIndex];
    setPhase({ type: "loading" });
    try {
      // Call previewDomain directly — domain is already known, no need for global /chat
      const reparsedBlock = await previewDomain(block.domain, correctedText.trim());
      const updatedDomains = [...response.domains];
      updatedDomains[domainIndex] = reparsedBlock;
      setPhase({ type: "preview", response: { ...response, domains: updatedDomains }, domainIndex });
    } catch (e) {
      setPhase({ type: "error", message: "Couldn't re-parse. Try different wording." });
    }
  };

  const s = makeStyles(colors);
  const title = domainLock
    ? domainLock.charAt(0).toUpperCase() + domainLock.slice(1)
    : "Log anything";
  const placeholder = domainLock === "health" ? "What did you eat?"
    : domainLock === "finance" ? "What did you spend?"
    : domainLock === "tasks" ? "What do you need to do?"
    : "Log a meal, expense, task…";

  return (
    <Modal visible={visible} animationType="slide" presentationStyle="pageSheet" onRequestClose={handleClose}>
      <KeyboardAvoidingView behavior={Platform.OS === "ios" ? "padding" : undefined} style={{ flex: 1 }}>
        <View style={s.container}>

          {/* Header */}
          <View style={s.header}>
            <Text style={s.headerTitle}>{title}</Text>
            <TouchableOpacity onPress={handleClose}>
              <Text style={s.cancel}>Cancel</Text>
            </TouchableOpacity>
          </View>

          <ScrollView style={{ flex: 1 }} contentContainerStyle={{ padding: 16 }} keyboardShouldPersistTaps="handled">

            {/* Idle / error */}
            {(phase.type === "idle" || phase.type === "error") && (
              <View>
                {phase.type === "error" && (
                  <Text style={{ color: colors.accentRed, marginBottom: 12 }}>{phase.message}</Text>
                )}
                <TextInput
                  style={s.input}
                  value={text}
                  onChangeText={setText}
                  placeholder={placeholder}
                  placeholderTextColor={colors.textTertiary}
                  multiline
                  autoFocus
                />
                <TouchableOpacity style={s.sendBtn} onPress={() => handleSend(text)}>
                  <Text style={s.sendBtnText}>Send</Text>
                </TouchableOpacity>
              </View>
            )}

            {/* Loading */}
            {phase.type === "loading" && (
              <View style={{ alignItems: "center", paddingTop: 40 }}>
                <ActivityIndicator size="large" color={colors.accent} />
                <Text style={{ color: colors.textSecondary, marginTop: 12 }}>Parsing…</Text>
              </View>
            )}

            {/* Preview */}
            {(phase.type === "preview" || phase.type === "confirming") && (
              <View>
                {/* Prose answer — persists even if user declines a domain write */}
                {phase.response.prose ? (
                  <View style={{ backgroundColor: colors.card, borderRadius: 12, padding: 16, marginBottom: 16 }}>
                    <Text style={{ color: colors.text, lineHeight: 22 }}>{phase.response.prose}</Text>
                    {phase.response.actions.map((action, i) => (
                      <TouchableOpacity key={i} style={s.actionBtn} onPress={() => {
                        setText(action.prefill);
                        setPhase({ type: "idle" });
                      }}>
                        <Text style={{ color: colors.accent }}>+ {action.label}</Text>
                      </TouchableOpacity>
                    ))}
                    {/* Prose-only: no domains to confirm — show Done */}
                    {phase.response.domains.length === 0 && (
                      <TouchableOpacity
                        style={[s.sendBtn, { marginTop: 16, backgroundColor: colors.cardElevated }]}
                        onPress={handleClose}
                      >
                        <Text style={[s.sendBtnText, { color: colors.text }]}>Done</Text>
                      </TouchableOpacity>
                    )}
                  </View>
                ) : null}

                {/* "Log all" shortcut when multiple domains */}
                {phase.type === "preview" && phase.response.domains.length > 1 && (
                  <TouchableOpacity
                    style={[s.sendBtn, { marginBottom: 12 }]}
                    onPress={() => handleLogAll(phase.response)}
                  >
                    <Text style={s.sendBtnText}>Log all ({phase.response.domains.length})</Text>
                  </TouchableOpacity>
                )}

                {/* Domain cards */}
                {phase.response.domains.map((block, i) => {
                  if (i < phase.domainIndex) return null; // already confirmed
                  if (i > phase.domainIndex) return (
                    <View key={i} style={{ opacity: 0.3 }}>
                      <View style={{ backgroundColor: colors.card, borderRadius: 12, padding: 16, marginBottom: 12 }}>
                        <Text style={{ color: colors.textSecondary }}>{block.domain} — pending</Text>
                      </View>
                    </View>
                  );
                  return (
                    <DomainPreviewCard
                      key={i}
                      block={block}
                      confirming={phase.type === "confirming" && phase.domainIndex === i}
                      onYes={() => handleYes(phase.response, i)}
                      onNo={() => handleNo(phase.response, i)}
                      colors={colors}
                    />
                  );
                })}
              </View>
            )}

            {/* Correction */}
            {phase.type === "correcting" && (
              <View>
                <Text style={{ color: colors.textSecondary, marginBottom: 8 }}>
                  Correct the {phase.response.domains[phase.domainIndex].domain} entry:
                </Text>
                <TextInput
                  style={s.input}
                  defaultValue={phase.prefill}
                  onChangeText={v => { correctionRef.current = v; }}
                  placeholder="Correct description…"
                  placeholderTextColor={colors.textTertiary}
                  multiline
                  autoFocus
                />
                <TouchableOpacity
                  style={s.sendBtn}
                  onPress={() => handleCorrectionSend(correctionRef.current, phase.response, phase.domainIndex)}
                >
                  <Text style={s.sendBtnText}>Re-parse</Text>
                </TouchableOpacity>
              </View>
            )}

            {/* Done */}
            {phase.type === "done" && (
              <View style={{ alignItems: "center", paddingTop: 40 }}>
                <Text style={{ color: colors.accentGreen, fontSize: 18, fontWeight: "600" }}>Logged ✓</Text>
              </View>
            )}

          </ScrollView>
        </View>
      </KeyboardAvoidingView>
    </Modal>
  );
}

function makeStyles(colors: any) {
  return StyleSheet.create({
    container: { flex: 1, backgroundColor: colors.background },
    header: {
      flexDirection: "row", justifyContent: "space-between", alignItems: "center",
      padding: 16, borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: colors.border,
    },
    headerTitle: { color: colors.text, fontSize: 17, fontWeight: "600" },
    cancel: { color: colors.accent, fontSize: 16 },
    input: {
      backgroundColor: colors.inputBg, borderRadius: 10, padding: 14,
      color: colors.text, fontSize: 16, minHeight: 80, textAlignVertical: "top", marginBottom: 12,
    },
    sendBtn: { backgroundColor: colors.accent, borderRadius: 10, padding: 14, alignItems: "center" },
    sendBtnText: { color: "#fff", fontWeight: "600", fontSize: 16 },
    actionBtn: { marginTop: 12, padding: 8 },
  });
}
```

- [ ] **Step 2: Verify TypeScript compiles**

```bash
cd ~/deep-workspace/chitiyu-pi/app && npx tsc --noEmit
```
Expected: no errors.

- [ ] **Step 3: Commit**

```bash
git add app/components/SmartInputSheet.tsx
git commit -m "feat(app): SmartInputSheet — Send button, prose-only Done, Log all, 1500ms close"
```

---

### Task 7: FAB in tab layout + per-tab sheet wiring

**Files:**
- Modify: `app/app/(tabs)/_layout.tsx`
- Modify: `app/app/(tabs)/health.tsx`
- Modify: `app/app/(tabs)/finance.tsx`
- Modify: `app/app/(tabs)/tasks.tsx`

The FAB lives in the tab layout (floats above all tabs). Uses `useSafeAreaInsets()` for safe bottom offset. Per-tab Log buttons open `SmartInputSheet` with `domainLock`.

- [ ] **Step 1: Replace `app/app/(tabs)/_layout.tsx`**

```typescript
import React, { useState } from "react";
import { View, TouchableOpacity, Text, StyleSheet } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { Tabs } from "expo-router";
import { Ionicons } from "@expo/vector-icons";
import { useTheme } from "../../lib/theme";
import { SmartInputSheet } from "../../components/SmartInputSheet";

type IoniconsName = React.ComponentProps<typeof Ionicons>["name"];

interface TabConfig {
  name: string;
  title: string;
  icon: IoniconsName;
  activeIcon: IoniconsName;
}

const TABS: TabConfig[] = [
  { name: "index",      title: "Insights",  icon: "bulb-outline",     activeIcon: "bulb"     },
  { name: "health",     title: "Health",    icon: "heart-outline",    activeIcon: "heart"    },
  { name: "finance",    title: "Finance",   icon: "wallet-outline",   activeIcon: "wallet"   },
  { name: "tasks",      title: "Tasks",     icon: "checkbox-outline", activeIcon: "checkbox" },
  { name: "knowledge",  title: "Knowledge", icon: "library-outline",  activeIcon: "library"  },
];

const TAB_BAR_HEIGHT = 49; // standard iOS tab bar height

export default function TabsLayout() {
  const { colors } = useTheme();
  const insets = useSafeAreaInsets();
  const [fabOpen, setFabOpen] = useState(false);

  const fabBottom = insets.bottom + TAB_BAR_HEIGHT + 16;

  return (
    <View style={{ flex: 1 }}>
      <Tabs
        screenOptions={{
          tabBarActiveTintColor: colors.accent,
          tabBarInactiveTintColor: colors.textSecondary,
          tabBarStyle: { backgroundColor: colors.tabBar, borderTopColor: colors.border },
          headerStyle: { backgroundColor: colors.background },
          headerTintColor: colors.text,
          headerTitleStyle: { fontWeight: "600" },
        }}
      >
        {TABS.map((tab) => (
          <Tabs.Screen
            key={tab.name}
            name={tab.name}
            options={{
              title: tab.title,
              tabBarIcon: ({ focused, color, size }) => (
                <Ionicons name={focused ? tab.activeIcon : tab.icon} size={size} color={color} />
              ),
            }}
          />
        ))}
      </Tabs>

      {/* FAB — always global, no domainLock */}
      <TouchableOpacity
        style={[s.fab, { backgroundColor: colors.accent, bottom: fabBottom }]}
        onPress={() => setFabOpen(true)}
        activeOpacity={0.85}
      >
        <Text style={s.fabIcon}>+</Text>
      </TouchableOpacity>

      <SmartInputSheet
        visible={fabOpen}
        onClose={() => setFabOpen(false)}
        onConfirmed={() => setFabOpen(false)}
      />
    </View>
  );
}

const s = StyleSheet.create({
  fab: {
    position: "absolute",
    right: 20,
    width: 56,
    height: 56,
    borderRadius: 28,
    alignItems: "center",
    justifyContent: "center",
    shadowColor: "#000",
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.3,
    shadowRadius: 6,
    elevation: 8,
  },
  fabIcon: { color: "#fff", fontSize: 28, fontWeight: "300", lineHeight: 32 },
});
```

- [ ] **Step 2: Wire `SmartInputSheet` into Health tab**

In `app/app/(tabs)/health.tsx`:

Add import at the top:
```typescript
import { SmartInputSheet } from "../../components/SmartInputSheet";
```

Add state in the component body:
```typescript
const [smartOpen, setSmartOpen] = useState(false);
```

Replace the existing log meal button's `onPress` with:
```typescript
onPress={() => setSmartOpen(true)}
```

Add before `</SafeAreaView>`:
```typescript
<SmartInputSheet
  visible={smartOpen}
  onClose={() => setSmartOpen(false)}
  onConfirmed={() => { setSmartOpen(false); loadData(); }}
  domainLock="health"
/>
```

(`loadData` is the existing function that reloads meals — already present in health.tsx.)

- [ ] **Step 3: Wire `SmartInputSheet` into Finance tab**

In `app/app/(tabs)/finance.tsx`:

```typescript
import { SmartInputSheet } from "../../components/SmartInputSheet";
// ...
const [smartOpen, setSmartOpen] = useState(false);
// Wire existing "Log Expense" button: onPress={() => setSmartOpen(true)}
// Add before </SafeAreaView>:
<SmartInputSheet
  visible={smartOpen}
  onClose={() => setSmartOpen(false)}
  onConfirmed={() => { setSmartOpen(false); loadData(); }}
  domainLock="finance"
/>
```

- [ ] **Step 4: Wire `SmartInputSheet` into Tasks tab**

In `app/app/(tabs)/tasks.tsx`:

```typescript
import { SmartInputSheet } from "../../components/SmartInputSheet";
// ...
const [smartOpen, setSmartOpen] = useState(false);
// Wire existing "Add Task" button: onPress={() => setSmartOpen(true)}
// Add before </SafeAreaView>:
<SmartInputSheet
  visible={smartOpen}
  onClose={() => setSmartOpen(false)}
  onConfirmed={() => { setSmartOpen(false); loadTasks(); }}
  domainLock="tasks"
/>
```

(`loadTasks` is the existing data-reload function in tasks.tsx.)

- [ ] **Step 5: Verify TypeScript compiles**

```bash
cd ~/deep-workspace/chitiyu-pi/app && npx tsc --noEmit
```
Expected: no errors.

- [ ] **Step 6: Run backend tests**

```bash
cd ~/deep-workspace/chitiyu-pi && uv run pytest -v
```
Expected: all tests pass.

- [ ] **Step 7: Commit**

```bash
git add app/app/(tabs)/_layout.tsx app/app/(tabs)/health.tsx app/app/(tabs)/finance.tsx app/app/(tabs)/tasks.tsx
git commit -m "feat(app): FAB with safe-area offset + SmartInputSheet on Health/Finance/Tasks tabs"
```

---

## Self-Review

**Review fixes applied:**

| Fix | Where |
|-----|-------|
| Button label "Send" (not "Parse & Preview") | Task 6 `SmartInputSheet` |
| Prose-only "Done" button | Task 6 preview phase, `domains.length === 0` guard |
| Finance fastPath via real `/finance/transactions/preview` endpoint | Task 4 (new endpoint) + Task 5 `previewDomain` |
| `_parse_transaction_text` → `parse_transaction_input` (public) | Task 2 (dedicated refactor task) |
| Correction re-parse uses `previewDomain` not global `/chat` | Task 6 `handleCorrectionSend` |
| "Log all" button when `domains.length > 1` | Task 6 preview phase |
| Success flash 1500ms (was 800ms) | Task 6 `handleYes` / `handleLogAll` |
| FAB `bottom` uses `useSafeAreaInsets()` | Task 7 `_layout.tsx` |
| Engine-level tests mocking at `call_claude` | Task 3 `test_build_chat_response_meal/finance` |

**Spec coverage check:**

| Requirement | Task |
|-------------|------|
| Tasks parsed intelligently, not stored as-is | Task 1 |
| Subtasks from comma-list | Task 1 parse prompt |
| Per-item due dates inferred | Task 1 parse prompt |
| Urgency → priority | Task 1 parse prompt |
| Recurring tasks via template+instances | Task 1 `create_tasks_from_input` |
| `parse_transaction_input` public interface | Task 2 |
| POST /chat global endpoint | Task 3 |
| Multi-domain single message | Task 3 `build_chat_response` |
| POST /chat/confirm per domain | Task 3 |
| Knowledge graph injected | Task 3 router semantic search |
| Query + write in same response | Task 3 prose + domains together |
| POST /finance/transactions/preview | Task 4 |
| api.ts types + all three functions | Task 5 |
| SmartInputSheet full flow | Task 6 |
| "Send" button label | Task 6 |
| Prose-only "Done" close path | Task 6 |
| Correction pre-filled with domain extract | Task 6 `handleNo` |
| Correction re-parse via `previewDomain` | Task 6 `handleCorrectionSend` |
| "Log all" bulk confirm | Task 6 |
| 1500ms success flash | Task 6 |
| FAB global, safe-area offset | Task 7 |
| Per-tab Log buttons domain-locked | Task 7 |
| "Log as task" action button | Task 6 prose card |
| Engine-level tests at `call_claude` level | Task 3 |

**Placeholder scan:** No TBD, no TODO, no "similar to Task N".

**Type consistency:**
- `parse_transaction_input` named consistently across Task 2 (rename), Task 3 (`chat.py` import), Task 4 (router import), Task 5 (`previewDomain` finance path)
- `DomainBlock.preview` typed as `DomainPreview = HealthPreview | FinancePreview | TaskPreviewItem[]` — consistent across Tasks 5, 6, 7
- `confirmDomain(domain, preview)` matches `ConfirmRequest` in Task 3
- `previewDomain` returns `DomainBlock` — consistent with what `SmartInputSheet` consumes in Task 6
