# Chitiyu PI — Developer Context

Personal intelligence app for Deepak. FastAPI backend + Expo React Native frontend (Expo Go on device).

## Stack

| Layer | Tech |
|-------|------|
| Backend | Python, FastAPI, SQLite (chitiyu.db), APScheduler, python-telegram-bot |
| Frontend | Expo SDK 54, React Native, TypeScript, Expo Router (file-based tabs) |
| LLM | Claude Haiku 4.5 (dispatch/classify), Claude Sonnet 4.6 (insights/polish/digest) |
| Auth | `X-API-Key` header on all backend routes |
| Deploy | launchd `com.chitiyu.bot`, port 8000 |

## Repo Layout

```
chitiyu-pi/
  backend/
    main.py                  # FastAPI app, router wiring, lifespan (scheduler + Telegram)
    config.py                # env vars: API_KEY, TELEGRAM_*, HA_*, DISPATCH_MODEL, POLISH_MODEL
    auth.py                  # verify_api_key dependency
    scheduler.py             # APScheduler cron: 8am digest, hourly meal nudge, 4pm overdue, 10pm journal
    db/
      schema.py              # All CREATE TABLE statements — single source of truth
      connection.py          # get_connection(path)
    domains/
      health/                # meals, recipes, health_metrics
      finance/               # accounts, transactions, budgets, balances, milestones, goals, net_worth
      tasks/                 # tasks (one-off) + task_templates/task_instances (recurring)
      knowledge/             # entities, facts, fields, relationships, events + sqlite-vec embeddings
      journal/               # journal_entries (date-keyed, raw + retro JSON)
    orchestrator/
      handler.py             # Main agent loop: tier1 → classify → knowledge inject → Haiku tool loop → Sonnet polish
      classifier.py          # Regex Tier 1 → Haiku fallback domain routing
      tier1.py               # Zero-LLM fast path: /done N, "show tasks", "lock door", garage
      digest.py              # Morning digest: Python numbers block + Sonnet paragraph
      insights.py            # Cross-domain insight cards (Sonnet) → insights table → insight_ready event
      insights_store.py      # Upsert/fetch insights by (user_id, scope)
      insights_router.py     # GET /insights/latest, POST /insights/generate (async thread)
      retro.py               # Evening retrospective engine
      dispatcher.py          # post_event() + dispatch_pending() → Telegram
      history.py             # HistoryManager — per-user conversation history
      embedder.py            # 384-dim embeddings for knowledge semantic search
      llm.py                 # call_claude() wrapper
    integrations/
      ha/                    # Home Assistant client (status, lock, restart, garage)
      siri/router.py         # /siri/log-meal, /siri/add-task, /siri/macros, /siri/sync-health
                             # NOTE: /siri/log-expense is a stub — not yet wired to finance tools
      calendar.py            # iCal/Google Calendar (CALENDAR_ICS_URL env var — NOT YET CONFIGURED)
      health_auto_export_router.py  # POST /integrations/health-auto-export — Health Auto Export iOS app push
  app/
    app/(tabs)/
      _layout.tsx            # 5 tabs: Insights, Health, Finance, Tasks, Knowledge
      index.tsx              # Insights tab — InsightCard list, scope toggle, generate + poll loop
      health.tsx             # Health tab — meal log (2-step preview/confirm), recipes, swipe-delete
      finance.tsx            # Finance tab — transactions, budget editor, category picker
      tasks.tsx              # Tasks tab — today/overdue/calendar with date dots
      knowledge.tsx          # Knowledge tab — entity list, semantic search
    components/
      InsightCard.tsx        # Expand/collapse (LayoutAnimation), dismiss, cycling accent colors
      MealRow.tsx            # Swipe-to-delete meal row
      TransactionRow.tsx     # Swipe-to-delete transaction row
      TaskRow.tsx
      MacroRings.tsx
      SwipeableRow.tsx
    lib/
      api.ts                 # Typed API client — all endpoints, all response types
      theme.ts               # Dark/light theme, useTheme() hook, colors.* tokens
      auth.ts                # API_URL + API_KEY from .env
      dateUtils.ts
    constants/targets.ts     # Biological targets: 1500 kcal, 155g protein, 45g fat, 117g carbs
```

## Domain Boundary Rule — Non-Negotiable

Each domain is a fake microservice:
1. No domain may import from another domain
2. No domain may query another domain's DB tables
3. All cross-domain work routes through `orchestrator/` only

```bash
# Verify: should only show same-domain imports
grep -r "from domains\." backend/domains/
```

## Message Flow

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

iPhone Health Auto Export → POST /integrations/health-auto-export → health_metrics table
Siri Shortcut → POST /siri/sync-health → health_metrics table

APScheduler → digest/nudge/retro → dispatcher → Telegram
Insights engine → assemble cross-domain context → Sonnet → insights table
```

## Scheduler Jobs

| Time | Job |
|------|-----|
| 8:00am | Morning digest → Telegram |
| 9am–10pm hourly | Meal nudge if no meal logged in past hour |
| 4:00pm | Overdue tasks nudge → Telegram |
| 10:00pm | Evening journal prompt if no entry today |
| 10:30pm | Evening journal follow-up if still no entry |

## Models

- `DISPATCH_MODEL = claude-haiku-4-5-20251001` — fast path: classify, tool dispatch, Siri spoken replies
- `POLISH_MODEL = claude-sonnet-4-6` — insight cards, morning digest paragraph, polish pass

## Deepak's Targets (for insights/digest context)

- Cut: 190 → 170 lbs over 10 weeks
- Calories: 1,500 kcal/day | Protein: 150–160g | Fat: 40–50g | Carbs: 110–125g
- Steps: 10,000/day | Deep sleep: 60+ min | Dinner cutoff: 6:30pm | Caffeine cutoff: 11am
- Discretionary budget: $800/mo | Savings goal: Chase Checking = $21,554.95 by Jan 29, 2027

## Open Items / Known Gaps

- **Meal time backdating** — selecting "Lunch" slot at 7pm logs wall-clock time → meal appears under Dinner bucket. Fix: when selected slot doesn't match current-hour's natural bucket, use slot midpoint time instead
- **CALENDAR_ICS_URL** — not configured; calendar integration exists but is inactive
- **Siri log-expense** — stub only; needs wiring to finance tools
- **Apple Health Shortcut** — Siri Shortcut not yet created on device
- **4 Siri Shortcuts** — log-meal, log-expense, add-task, macros — not yet set up on device

## Running Locally

```bash
# Backend
cd ~/deep-workspace/chitiyu-pi
uv run python backend/main.py         # dev
launchctl start com.chitiyu.bot       # prod (launchd)
launchctl stop com.chitiyu.bot        # stop prod

# Frontend
cd ~/deep-workspace/chitiyu-pi/app
npx expo start                        # scan QR in Expo Go

# Tests
cd ~/deep-workspace/chitiyu-pi
uv run pytest                         # 162 tests
```

## Key Env Vars (.env at repo root)

```
API_KEY=...
TELEGRAM_BOT_TOKEN=...
TELEGRAM_CHAT_ID=...
HA_URL=...
HA_TOKEN=...
CALENDAR_ICS_URL=  # not yet set
DB_FILENAME=chitiyu.db
```
