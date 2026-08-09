# chitiyu-pi

Personal intelligence app — connecting the dots across health, finance, tasks, and knowledge.

FastAPI backend + Expo React Native frontend + Telegram bot, all running on a Mac mini at home.

---

## What it does

- **Tasks** — One-off and recurring tasks (daily/weekly/monthly/yearly), priority levels, calendar with date indicator dots
- **Health** — Meal logging with macros, recipe library, health metrics (steps, sleep, resting HR) from Apple Health
- **Finance** — Transaction log, budget tracking by category/type, savings goals, net worth milestones
- **Knowledge** — Personal knowledge graph: entities, facts, relationships, semantic search via embeddings
- **Journal** — Daily journal entries with evening prompts and nightly retrospective
- **Insights** — Cross-domain AI insight cards (Claude Sonnet), generated on demand or on schedule
- **Telegram bot** — Natural language interface to all domains; morning digest, overdue nudges, evening journal prompt

---

## Stack

| Layer | Tech |
|-------|------|
| Backend | Python, FastAPI, SQLite, APScheduler |
| Frontend | Expo SDK 54, React Native, TypeScript, Expo Router |
| Bot | python-telegram-bot |
| LLM | Claude Haiku 4.5 (dispatch/classify) · Claude Sonnet 4.6 (insights/digest/polish) |
| Auth | `X-API-Key` header on all routes |
| Deploy | macOS launchd (`com.chitiyu.bot`), port 8000 |

---

## Repo layout

```
chitiyu-pi/
  backend/
    main.py                  # FastAPI app + lifespan (scheduler + Telegram bot)
    config.py                # env vars
    scheduler.py             # APScheduler: 8am digest, hourly meal nudge, 4pm overdue, 10pm journal
    db/
      schema.py              # All CREATE TABLE statements — single source of truth
      connection.py          # get_connection(path)
    domains/
      health/                # meals, recipes, health_metrics
      finance/               # accounts, transactions, budgets, balances, milestones, net_worth
      tasks/                 # tasks (one-off) + task_templates/task_instances (recurring)
      knowledge/             # entities, facts, fields, relationships, events + sqlite-vec embeddings
      journal/               # journal_entries (date-keyed, raw + retro JSON)
    orchestrator/
      handler.py             # Agent loop: tier1 → classify → knowledge inject → Haiku tool loop → Sonnet polish
      classifier.py          # Regex tier1 → Haiku fallback domain routing
      tier1.py               # Zero-LLM fast path: /done N, "show tasks", HA controls
      digest.py              # Morning digest: numbers block + Sonnet paragraph
      insights.py            # Cross-domain insight cards (Sonnet)
      retro.py               # Evening retrospective engine
      dispatcher.py          # post_event() + dispatch_pending() → Telegram
      history.py             # Per-user conversation history
      embedder.py            # 384-dim embeddings for knowledge semantic search
      llm.py                 # call_claude() wrapper
    integrations/
      ha/                    # Home Assistant client (status, lock, garage, restart)
      siri/router.py         # /siri/log-meal, /siri/add-task, /siri/macros, /siri/sync-health
      health_auto_export_router.py  # POST /integrations/health-auto-export (Health Auto Export iOS app)
  app/
    app/(tabs)/
      index.tsx              # Insights tab
      health.tsx             # Health tab — meal log, recipes, macros
      finance.tsx            # Finance tab — transactions, budgets, milestones
      tasks.tsx              # Tasks tab — today/overdue/calendar with date dots + recurring
      knowledge.tsx          # Knowledge tab — entity list, semantic search
    components/
      InsightCard.tsx        # Expand/collapse, dismiss, cycling accent colors
      TaskRow.tsx            # Priority dot, swipe-to-delete, uid-based routing
      TransactionRow.tsx     # Swipe-to-delete
      MealRow.tsx
      MacroRings.tsx
      SwipeableRow.tsx
    lib/
      api.ts                 # Typed API client — all endpoints + response types
      theme.ts               # Dark/light theme, useTheme() hook
      dateUtils.ts           # Local-time utilities (todayLocal, parseLocalTs)
      auth.ts                # API_URL + API_KEY from .env
```

---

## Architecture

### Domain boundary rule — non-negotiable

Each domain in `backend/domains/` is a fake microservice:

1. No domain may import from another domain
2. No domain may query another domain's DB tables
3. All cross-domain work routes through `orchestrator/` only

```bash
# Verify — should only show same-domain imports
grep -r "from domains\." backend/domains/
```

### Message flow

```
Telegram → bot/handlers.py → handle_message()
  → tier1 (zero-LLM exact match) → return
  → classify() → domain selection
  → knowledge semantic search (top 5 facts injected)
  → domain.inject_context() + domain.build_system_prompt()
  → Haiku tool loop (max 10 rounds, 120s timeout)
  → Sonnet polish pass
  → reply via Telegram

Expo app → lib/api.ts → FastAPI routers → domain db layer → SQLite

iPhone Health Auto Export → POST /integrations/health-auto-export → health_metrics
Siri Shortcut → POST /siri/sync-health → health_metrics
```

### Scheduled jobs

| Time | Job |
|------|-----|
| 8:00am | Morning digest → Telegram |
| 9am–10pm hourly | Meal nudge if no meal logged in past hour |
| 4:00pm | Overdue tasks nudge → Telegram |
| 10:00pm | Evening journal prompt if no entry today |
| 10:30pm | Evening journal follow-up if still no entry |

---

## Running locally

```bash
# Backend
cd ~/deep-workspace/chitiyu-pi
uv run python backend/main.py         # dev
launchctl start com.chitiyu.bot       # prod
launchctl stop com.chitiyu.bot        # stop prod

# Frontend
cd ~/deep-workspace/chitiyu-pi/app
npx expo start                        # scan QR in Expo Go

# Tests
cd ~/deep-workspace/chitiyu-pi
uv run pytest                         # ~160 tests
```

---

## Environment variables

Create a `.env` file at the repo root:

```
API_KEY=...
TELEGRAM_BOT_TOKEN=...
TELEGRAM_CHAT_ID=...
HA_URL=...
HA_TOKEN=...
CALENDAR_ICS_URL=       # optional — iCal/Google Calendar feed
DB_FILENAME=chitiyu.db
```

---

## Models

- `DISPATCH_MODEL = claude-haiku-4-5-20251001` — classify, tool dispatch, Siri spoken replies
- `POLISH_MODEL = claude-sonnet-4-6` — insight cards, morning digest, polish pass
