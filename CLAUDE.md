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
                             # GET /health/insights-context?days=7 — aggregated trends for insights engine
                             # POST /health/meals/preview — dry-run parse NL → {description,calories,protein,fat,carbs}
                             # parse_meal_macros(text, context="") → dict | None  (public, called by chat.py)
      finance/               # accounts, transactions, budgets, balances, milestones, goals, net_worth
                             # GET /finance/insights-context — Chase/PNC balances, discretionary trend, milestone curve, envelopes
                             # POST /finance/transactions/preview — dry-run parse NL → {description,amount,category,date}
                             # parse_transaction_input(text, context="") → dict | None  (public, called by chat.py)
                             # budgets.budget_type: fixed|recurring|discretionary|envelope
                             # budgets.period: monthly|weekly|biannual|annual
      tasks/                 # tasks (one-off) + task_templates/task_instances (recurring)
                             # parse_task_input(text, today=None) → list[dict]  — NL → [{title,due_at,priority,recurrence,anchor_date}]
                             # create_tasks_from_input(conn, user_id, text) → list[dict]  — parse + insert all tasks/templates
                             # POST /tasks/ now routes through create_tasks_from_input (LLM parses, not literal insert)
      knowledge/             # entities, facts, fields, relationships, events + sqlite-vec embeddings
                             # GET /knowledge/entities — returns entities with fact_count (LEFT JOIN facts)
                             # GET /knowledge/search?q= — semantic search via 384-dim embeddings
      journal/               # journal_entries (date-keyed, raw + retro JSON)
    orchestrator/
      handler.py             # Main agent loop: tier1 → classify → knowledge inject → Haiku tool loop → Sonnet polish
      classifier.py          # Regex Tier 1 → Haiku fallback domain routing
      tier1.py               # Zero-LLM fast path: /done N, "show tasks", "lock door", garage
      chat.py                # build_chat_response() — single Haiku intent call → domain parsers → ChatResponse
                             # ChatResponse: {prose, domains:[{domain,preview,extract}], actions:[]}
      chat_router.py         # POST /chat — multi-domain NL input; POST /chat/confirm — per-domain commit
                             # /chat/confirm: health→insert_meal, finance→insert_transaction, tasks→insert_task/template
      digest.py              # Morning digest: Python numbers block + Sonnet paragraph
      insights.py            # Cross-domain insight cards (Sonnet) → insights table → insight_ready event
                             # System prompt contains Deepak's full profile (paycheck, targets, mortgage structure)
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
                             # Global FAB (bottom-right) — opens SmartInputSheet with no domainLock
                             # FAB bottom = useSafeAreaInsets().bottom + TAB_BAR_HEIGHT(49) + 16
      index.tsx              # Insights tab — InsightCard list, scope toggle, generate + poll loop
      health.tsx             # Health tab — meal log via SmartInputSheet (domainLock="health"), recipes, swipe-delete
      finance.tsx            # Finance tab — smart hero (discretionary + milestone), typed budget accordions
                             # Log Expense → SmartInputSheet (domainLock="finance")
      tasks.tsx              # Tasks tab — today/overdue/calendar with date dots
                             # Add Task → SmartInputSheet (domainLock="tasks")
      knowledge.tsx          # Knowledge tab — entity list, semantic search
    components/
      InsightCard.tsx        # Expand/collapse (LayoutAnimation), dismiss, cycling accent colors
      MealRow.tsx            # Swipe-to-delete meal row
      TransactionRow.tsx     # Swipe-to-delete transaction row
      TaskRow.tsx
      MacroRings.tsx
      SwipeableRow.tsx
      SmartInputSheet.tsx    # Global NL input modal: idle→loading→preview→confirm/correct→done state machine
                             # Props: visible, onClose, onConfirmed, domainLock?, initialText?
                             # domainLock: routes to domain-specific preview endpoint (fast path)
                             # No domainLock: routes to POST /chat (multi-domain global)
                             # "Log all" fires all domain confirms in parallel (Promise.all)
                             # Correction re-parse: previewDomain(block.domain, correctedText) — not chatMessage
    lib/
      api.ts                 # Typed API client — all endpoints, all response types
                             # chatMessage(text) → ChatResponse
                             # confirmDomain(domain, preview, user_id?) → ConfirmResult
                             # previewDomain(domain, text) → DomainBlock  (health/finance→domain endpoint; tasks→/chat)
                             # Types: ChatResponse, DomainBlock, DomainName, DomainPreview, HealthPreview,
                             #        FinancePreview, TaskPreviewItem, ChatAction, ConfirmResult
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

Expo app (domain tab Log button) → previewDomain(domain, text)
  → POST /health/meals/preview  OR  /finance/transactions/preview  OR  /chat (tasks fallback)
  → SmartInputSheet preview card → user confirms
  → confirmDomain(domain, preview) → POST /chat/confirm → domain db insert

Expo app (global FAB) → chatMessage(text) → POST /chat
  → build_chat_response(): Haiku intent call → domain parsers (parse_meal_macros, parse_transaction_input, parse_task_input)
  → ChatResponse {prose, domains[], actions[]}
  → SmartInputSheet: sequential domain preview/confirm OR "Log all" parallel confirm
  → POST /chat/confirm per domain → domain db insert + trigger_insights_async

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
- **Discretionary budget: $900/mo** — groceries $200, dining $150, shopping $150, fuel $100, misc $200, home $100
- Savings goal: Chase Checking = $21,554.95 by Jan 29, 2027

### Financial System

- **Paycheck:** $3,949.62 bi-weekly net take-home (Deepak). Paydays alternate — use milestone curve to identify paycheck dates.
- **Other income:** Bunny $2,250/mo + renters $2,750/mo = $5,000/mo household contribution
- **Mortgages:** Primary $4,300/mo + rental $2,300/mo (rental income $2,750 → net +$450 on rental)
- **Savings:** $2,000/month PNC transfer — auto-transfer on the 4th of each month (NOT per paycheck)
- **Milestone curve:** tracks Chase Checking balance bi-weekly. `current_balance` in milestones = Chase Checking ONLY (not liquid position). Milestone table has recurring tasks to confirm on paycheck day.
- **Envelope budgets (6-month pools):** travel $10,000 | insurance $2,500 | gifts $1,500
- **Fixed/recurring:** car $563, utilities $350, subscriptions $122 — not tracked as monthly spend, just reference

## Open Items / Known Gaps

Full backlog lives in project memory: `~/.claude/projects/-Users-me-deep-workspace-chitiyu/memory/enhancements.md`

**Critical:**
- **Health sync (iOS → backend)** — Steps, sleep, HR all show "—". iOS Shortcuts "Find Health Samples" hangs. Needs EAS dev build (native HealthKit) or Health Auto Export alternative. Highest priority gap.
- **Meal time backdating** — selecting "Lunch" at 7pm logs wall-clock time → meal appears under Dinner bucket. Fix: use slot midpoint (12:00 for lunch) when wall-clock doesn't match selected slot. `app/lib/dateUtils.ts slotISO()`
- **SmartInputSheet partial log-all failure** — if one confirmDomain fails mid-flight, UI resets to idle; server rows already persisted; no recovery UX. `SmartInputSheet.tsx:167`
- **Recurring task advance_days hardcoded to 1** — "Show in advance" toggle doesn't wire value to API. `chat_router.py:94`
- **Task template delete removes only one instance** — no UI to delete entire recurring series. `tasks.tsx:447`

**Quick wins pending:**
- **Siri log-expense** — stub only (`siri/router.py:89`); needs wiring to `parse_transaction_input` + `insert_transaction`
- **tasks.tsx dead modal** — old Add Task inline sheet (openSheet state + ~80 lines) unreachable; safe to delete
- **Finance account delete** — no swipe-delete UI on accounts
- **Budget $0 validation** — Save enabled with amount=0; should be disabled
- **CALENDAR_ICS_URL** — not configured; calendar integration inactive

**By design:**
- **Finance: log discretionary manually** — Fixed/recurring costs not tracked as transactions (intentional)
- **POST /tasks/ always LLM-parses** — `body.due_at` and `body.priority` silently ignored; LLM infers from title text. Programmatic callers must use text-only intent.

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
uv run pytest                         # 210 tests
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
