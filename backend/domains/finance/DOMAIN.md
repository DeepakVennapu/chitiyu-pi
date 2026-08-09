# Finance Domain

## Overview

Tracks Deepak's financial system: account balances, discretionary spending, envelope budgets, and milestone curve progress toward the Chase Checking goal.

**Design rule:** only the orchestrator crosses domain lines. This file documents everything a future developer needs to maintain the finance domain without reading any other domain.

---

## Financial System Model

### Income

| Source | Amount | Frequency |
|--------|--------|-----------|
| Deepak paycheck | $3,949.62 net | Bi-weekly |
| Bunny contribution | $2,250.00 | Monthly |
| Rental income | $2,750.00 | Monthly |
| **Total household** | **~$10,320/mo** | — |

### Fixed Obligations

| Expense | Amount | Notes |
|---------|--------|-------|
| Primary mortgage | $4,300/mo | — |
| Rental mortgage | $2,300/mo | Covered by $2,750 rent → net +$450 |
| Car payment | $563/mo | — |
| Utilities | $350/mo | — |
| Subscriptions | $122/mo | — |
| Savings transfer (PNC) | $2,000/mo | Auto-transfer on the 4th of each month |

### Discretionary Budget: $900/month

The **only controllable variable**. Overspending this is the primary risk to the Jan 29, 2027 goal.

| Category | Budget |
|----------|--------|
| groceries | $200 |
| dining | $150 |
| shopping | $150 |
| fuel | $100 |
| misc | $200 |
| home | $100 |

**Logging model:** Deepak logs discretionary transactions manually through the app whenever a purchase happens. Fixed/recurring obligations are NOT tracked as transactions — they're reference data only.

### Envelope Budgets (6-month pools)

| Category | Pool | Period |
|----------|------|--------|
| travel | $10,000 | biannual |
| insurance | $2,500 | biannual |
| gifts | $1,500 | biannual |

Envelope spend is tracked as YTD transactions against the category. `get_envelope_spend()` returns remaining pool.

---

## Milestone Curve

**Goal:** Chase Checking = $21,554.95 by **2027-01-29**.

The milestone curve tracks Chase Checking balance bi-weekly on paycheck days. Each row in `financial_milestones` is one paycheck period:

- `target_date` — the paycheck date
- `expected_net_worth` — the Chase Checking target on that date (pre-computed from Excel)
- `actual_net_worth` — stamped manually after each paycheck (field name is a legacy misnomer; it tracks Chase Checking balance, not true net worth)
- `current_balance` — injected at query time from `account_balances` (latest Chase Checking row)

### Milestone Delta Pattern (from Excel)

Paycheck periods alternate between two patterns:
- **Paycheck period** (+$2,455): net of $3,949.62 paycheck minus ~$1,494 mid-month expenses
- **Bill period** (−$1,258): net of $3,949.62 paycheck minus ~$5,207 beginning-of-month expenses (mortgage etc.)

Use the milestone curve itself to identify paycheck dates — do not hardcode dates.

### Milestone Confirmation Tasks

Recurring tasks are seeded in the tasks domain to confirm Chase Checking balance on each paycheck day. These fire bi-weekly and prompt Deepak to update `actual_net_worth` via `/finance/milestones/{target_date}`.

**Important:** The `current_balance` field in `get_next_milestone()` is Chase Checking ONLY — not liquid position (checking + savings - credit). Milestone targets were built against Chase Checking exclusively.

---

## Budget Type Schema

`budgets.budget_type` — enforced via CHECK constraint:

| Value | Meaning |
|-------|---------|
| `discretionary` | Monthly spend categories Deepak controls |
| `envelope` | 6-month pools (travel, insurance, gifts) |
| `fixed` | Fixed monthly obligations (reference only, not tracked as spend) |
| `recurring` | Recurring non-discretionary costs (reference only) |

`budgets.period` — `monthly` | `weekly` | `biannual` | `annual`

Budget type classification is enforced at upsert via `upsert_budget(budget_type=...)`. The summary endpoint groups by type into `by_type: {fixed, recurring, discretionary, envelope}`.

### Categories NOT in budgets table

Intentionally excluded:
- **income/savings** — were spreadsheet artifacts, not spend categories. Deleted.
- **family $583** — never existed in Deepak's actual expense sheet. Phantom row, deleted.
- Monthly savings transfer ($2,000) — tracked via PNC balance growth, not as a transaction.

---

## Accounts in DB

| Account | Type | Role |
|---------|------|------|
| Chase Checking | checking | Primary checking; milestone target account |
| PNC | savings | Savings accumulator — should grow ~$2,000/month |
| Credit cards | credit | Subtracted in net worth computation |

`compute_net_worth_from_balances()` sums all accounts: credit accounts subtract, all others add.

`get_next_milestone()` does a specific JOIN: `LOWER(a.name) LIKE '%chase%' AND a.type='checking'` to get the Chase Checking balance. If the account is renamed, this query breaks.

---

## Key DB Functions

### `get_discretionary_total(conn, user_id, year, month) → (spent, budget)`
Returns total spent and total budget for all `budget_type='discretionary'` categories for the given month. Amounts are positive (absolute spend values).

### `get_envelope_spend(conn, user_id) → list[dict]`
Returns YTD spend vs pool for each `budget_type='envelope'` category:
```python
{"category": "travel", "pool": 10000, "period": "biannual",
 "spent_ytd": 1200.0, "remaining": 8800.0}
```

### `get_next_milestone(conn, user_id) → dict | None`
Returns the next upcoming `financial_milestones` row, augmented with `current_balance` from the latest Chase Checking entry in `account_balances`.

### `get_monthly_spend(conn, user_id, year, month) → dict[str, float]`
Returns `{category: total_spent}` for negative-amount transactions (expenses) in the month. Spend values are returned as positive numbers.

### `upsert_budget(conn, user_id, category, amount, period, budget_type)`
Upserts on `(user_id, category, period)` unique constraint. Always lowercase-strip the category before calling.

### `compute_net_worth_from_balances(conn, user_id) → float | None`
Derives net worth from latest `account_balances` rows. Credit account balances subtract; all others add.

---

## Transaction Sign Convention

- **Expenses:** negative amount (e.g., `-45.00` for a $45 purchase)
- **Income/deposits:** positive amount

`get_monthly_spend()` filters `amount < 0` and returns `abs(total)` — so all values in spend dicts are positive.

`EXCLUDED_FROM_TOTAL = {"income", "savings"}` — these categories are excluded from total spend calculations in the summary endpoint.

---

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/finance/accounts` | List all accounts |
| `POST` | `/finance/accounts` | Create account |
| `GET` | `/finance/balances/latest` | Latest balance per account + computed net worth |
| `GET` | `/finance/balances/history` | Balance history (optional account_id filter) |
| `POST` | `/finance/balances` | Bulk upsert balances for a date; auto-snapshots net worth |
| `GET` | `/finance/milestones` | All milestones (optional period_label filter) |
| `POST` | `/finance/milestones` | Create/update milestone |
| `PATCH` | `/finance/milestones/{target_date}` | Stamp actual Chase Checking balance |
| `GET` | `/finance/transactions` | List transactions (date_from, date_to, category, limit) |
| `POST` | `/finance/transactions` | Log transaction — NL text (Haiku-parsed) or structured |
| `DELETE` | `/finance/transactions/{id}` | Delete transaction |
| `POST` | `/finance/import/csv` | Import CSV; optional transform= for bank-specific formats |
| `GET` | `/finance/summary/{year}/{month}` | Budget summary with by_type grouping and milestone |
| `GET` | `/finance/insights-context` | Rich context for insights engine (see below) |
| `GET` | `/finance/budgets` | List all budgets |
| `POST` | `/finance/budgets` | Create/update budget (upserts on category+period) |
| `GET` | `/finance/networth` | Latest net worth snapshot |
| `POST` | `/finance/networth` | Record net worth snapshot |
| `GET` | `/finance/goals` | List savings goals |
| `POST` | `/finance/goals` | Create savings goal |
| `PATCH` | `/finance/goals/{id}` | Update goal progress |

---

## `/finance/insights-context` Response Shape

Used by `orchestrator/insights.py` to build the insights prompt. Returns everything needed to evaluate financial health:

```json
{
  "as_of": "2026-08-08",
  "chase_checking": {"balance": 11572.0, "date": "2026-07-31"},
  "pnc_savings": {"balance": 8000.0, "date": "2026-08-04"},
  "net_worth": 42000.0,
  "discretionary": {
    "this_month": {"spent": 340.0, "budget": 900.0, "remaining": 560.0},
    "trend_3mo": [
      {"month": "2026-06", "spent": 820, "budget": 900, "pct_used": 91.1},
      ...
    ],
    "categories": [
      {"category": "groceries", "spent": 120.0, "budget": 200.0, "over_budget": false},
      ...
    ]
  },
  "milestone": {
    "goal": "Chase Checking = $21,554.95 by 2027-01-29",
    "next": {"target_date": "2026-08-14", "expected_net_worth": 14370.0, "current_balance": 11572.0},
    "recent_history": [
      {"date": "2026-07-31", "target": 11117.0, "actual": 11572.0,
       "delta": 455.0, "status": "ahead"}
    ],
    "upcoming": [
      {"date": "2026-08-14", "target": 14370.0}
    ]
  },
  "envelopes": [
    {"category": "travel", "pool": 10000, "spent_ytd": 0, "remaining": 10000}
  ],
  "accounts": [
    {"name": "Chase Checking", "type": "checking", "balance": 11572.0, "as_of": "2026-07-31"}
  ]
}
```

---

## `/finance/summary/{year}/{month}` Response Shape

```json
{
  "year": 2026, "month": 8,
  "total_spent": 340.0, "total_budget": 900.0,
  "discretionary_spent": 340.0, "discretionary_budget": 900.0,
  "next_milestone": {"target_date": "2026-08-14", "expected_net_worth": 14370.0, "current_balance": 11572.0},
  "categories": [...],
  "by_type": {
    "fixed": [],
    "recurring": [],
    "discretionary": [...],
    "envelope": [...]
  }
}
```

---

## Frontend Integration

`finance.tsx` uses a two-part hero card:
1. **Discretionary progress** — `discretionary_spent / discretionary_budget` as a progress bar
2. **Milestone current/target** — `current_balance / expected_net_worth` from `next_milestone`

Budget editor has type picker pills (`discretionary` | `envelope` | `fixed` | `recurring`) and period picker (envelope-only: `biannual` | `annual`). Category is normalized to lowercase on the backend before upsert.

Four accordion sections in the finance tab: Discretionary (default open), Envelopes (6-month pools), Fixed, Recurring. Recurring section will render empty until real recurring spend categories are added — consider hiding empty sections.

---

## Known Issues / Gaps

- **Recurring accordion empty** — `family $583` was a phantom row (never in Deepak's actual sheet), deleted. No real recurring spend categories exist yet.
- **Milestone `actual_net_worth` field name** — misleading; it stores Chase Checking balance, not net worth. Renaming requires a migration.
- **CSV import transforms** — transform files in `domains/finance/transforms/` map bank-specific CSV columns to canonical format. Not all banks have transforms written.
- **Siri log-expense** — the `/siri/log-expense` endpoint is a stub; not yet wired to finance tools.
