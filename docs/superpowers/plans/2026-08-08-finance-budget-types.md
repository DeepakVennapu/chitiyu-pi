# Finance Budget Types & Smart Hero Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `budget_type` (fixed/recurring/discretionary/envelope) and `period` (monthly/biannual) to budgets, then redesign the finance hero card to show discretionary spend + next milestone checkpoint in one glance.

**Architecture:** Schema migration adds two columns to `budgets` table. Backend summary endpoint groups categories by type and computes per-type totals. Frontend hero becomes a single two-part card (discretionary progress + next milestone sentence); accordion sections group by budget_type with headers.

**Tech Stack:** SQLite (migration via Python script), FastAPI, Expo React Native, TypeScript

## Global Constraints

- SQLite: no ALTER COLUMN — use rename+recreate pattern for schema changes
- All category names stored lowercase in DB
- Backend runs via `uv run python backend/main.py` from `/Users/me/deep-workspace/chitiyu-pi`
- Frontend: Expo managed, no native modules, `colors.*` from `useTheme()` for all colors
- API key header: `x-api-key: chitiyu-2026`
- Base URL: `http://localhost:8000`
- DB path: `/Users/me/deep-workspace/chitiyu-pi/chitiyu.db`

---

## File Map

| File | Change |
|---|---|
| `backend/db/schema.py` | Add `budget_type` + `period` columns to budgets table DDL |
| `backend/db/migrate_budget_types.py` | One-shot migration script — rename, recreate, backfill, seed envelope budgets |
| `backend/domains/finance/db.py` | Update `upsert_budget`, `list_budgets` signatures; add `get_discretionary_summary`, `get_next_milestone` |
| `backend/domains/finance/router.py` | Update `budget_summary` response shape; add `budget_type`/`period` to `BudgetCreate` model |
| `app/lib/api.ts` | Update `CategoryBudget`, `Budget`, `FinanceSummary` interfaces; add `setBudgetType` call |
| `app/app/(tabs)/finance.tsx` | Replace hero, restructure accordion sections by budget_type |

---

## Task 1: Schema migration — add budget_type and period columns

**Files:**
- Modify: `backend/db/schema.py`
- Create: `backend/db/migrate_budget_types.py`

**Interfaces:**
- Produces: `budgets` table with columns `budget_type TEXT NOT NULL DEFAULT 'discretionary' CHECK(budget_type IN ('fixed','recurring','discretionary','envelope'))` and updated `period CHECK(period IN ('monthly','weekly','biannual','annual'))`

- [ ] **Step 1: Update schema.py DDL**

In `backend/db/schema.py`, replace the budgets table definition:

```python
        CREATE TABLE IF NOT EXISTS budgets (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id      INTEGER NOT NULL DEFAULT 1,
            category     TEXT NOT NULL,
            amount       REAL NOT NULL,
            period       TEXT NOT NULL DEFAULT 'monthly'
                         CHECK(period IN ('monthly','weekly','biannual','annual')),
            budget_type  TEXT NOT NULL DEFAULT 'discretionary'
                         CHECK(budget_type IN ('fixed','recurring','discretionary','envelope')),
            start_date   TEXT NOT NULL DEFAULT (date('now')),
            UNIQUE(user_id, category, period)
        );
```

- [ ] **Step 2: Write migration script**

Create `backend/db/migrate_budget_types.py`:

```python
"""One-shot migration: add budget_type + updated period CHECK to budgets table,
then backfill known categories and seed envelope budgets."""
import sqlite3, sys
from pathlib import Path

DB = Path(__file__).parent.parent.parent / "chitiyu.db"

CATEGORY_TYPES = {
    # fixed — non-negotiable, same every month
    "mortgage":      ("fixed",        "monthly"),
    "car":           ("fixed",        "monthly"),
    "utilities":     ("fixed",        "monthly"),
    "subscriptions": ("fixed",        "monthly"),
    # recurring — planned, monthly
    "family":        ("recurring",    "monthly"),
    "savings":       ("recurring",    "monthly"),
    "income":        ("recurring",    "monthly"),
    # discretionary — daily decisions
    "groceries":     ("discretionary","monthly"),
    "dining":        ("discretionary","monthly"),
    "shopping":      ("discretionary","monthly"),
    "misc":          ("discretionary","monthly"),
    "fuel":          ("discretionary","monthly"),
    # envelope — 6-month pools
    "travel":        ("envelope",     "biannual"),
    "insurance":     ("envelope",     "biannual"),
    "gifts":         ("envelope",     "biannual"),
}

# Envelope amounts for 6-month period (from spreadsheet)
ENVELOPE_AMOUNTS = {
    "travel":    10000.00,
    "insurance":  2500.00,
    "gifts":      1500.00,
}

def run():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row

    # Save existing rows
    rows = [dict(r) for r in conn.execute("SELECT * FROM budgets").fetchall()]
    print(f"Migrating {len(rows)} existing budget rows...")

    conn.executescript("""
        PRAGMA foreign_keys=OFF;
        ALTER TABLE budgets RENAME TO budgets_old;
        CREATE TABLE budgets (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id      INTEGER NOT NULL DEFAULT 1,
            category     TEXT NOT NULL,
            amount       REAL NOT NULL,
            period       TEXT NOT NULL DEFAULT 'monthly'
                         CHECK(period IN ('monthly','weekly','biannual','annual')),
            budget_type  TEXT NOT NULL DEFAULT 'discretionary'
                         CHECK(budget_type IN ('fixed','recurring','discretionary','envelope')),
            start_date   TEXT NOT NULL DEFAULT (date('now')),
            UNIQUE(user_id, category, period)
        );
        PRAGMA foreign_keys=ON;
    """)

    # Restore existing rows with correct budget_type and period
    for r in rows:
        cat = r["category"].lower().strip()
        btype, period = CATEGORY_TYPES.get(cat, ("discretionary", "monthly"))
        # Envelope categories get their 6-month amount, not the old monthly amortization
        amount = ENVELOPE_AMOUNTS.get(cat, r["amount"]) if btype == "envelope" else r["amount"]
        conn.execute(
            """INSERT OR IGNORE INTO budgets(user_id, category, amount, period, budget_type, start_date)
               VALUES (?,?,?,?,?,?)""",
            (r["user_id"], cat, amount, period, btype, r.get("start_date", "2026-08-08"))
        )

    conn.commit()

    final = conn.execute("SELECT category, amount, period, budget_type FROM budgets ORDER BY budget_type, category").fetchall()
    print(f"\nMigrated {len(final)} budget rows:")
    for r in final:
        print(f"  [{r['budget_type']:14s}] {r['category']:16s}  ${r['amount']:>9,.2f}  / {r['period']}")

    conn.close()
    print("\nDone.")

if __name__ == "__main__":
    run()
```

- [ ] **Step 3: Run the migration**

```bash
cd /Users/me/deep-workspace/chitiyu-pi
.venv/bin/python3 backend/db/migrate_budget_types.py
```

Expected output shows all 14 rows migrated with correct types. Travel/insurance/gifts should show biannual period and full 6-month amounts.

- [ ] **Step 4: Verify in SQLite**

```bash
cd /Users/me/deep-workspace/chitiyu-pi && .venv/bin/python3 -c "
import sqlite3
conn = sqlite3.connect('chitiyu.db')
rows = conn.execute('SELECT category, amount, period, budget_type FROM budgets ORDER BY budget_type, category').fetchall()
for r in rows: print(r)
"
```

Expected: 14 rows, envelopes have `biannual` period and amounts 10000/2500/1500.

---

## Task 2: Backend — update summary endpoint and db functions

**Files:**
- Modify: `backend/domains/finance/db.py`
- Modify: `backend/domains/finance/router.py`

**Interfaces:**
- Consumes: migrated `budgets` table with `budget_type` + `period` columns
- Produces:
  - `GET /finance/summary/{year}/{month}` response adds `by_type` dict and `next_milestone` object
  - `POST /finance/budgets` accepts `budget_type: str = "discretionary"` and `period: str = "monthly"`
  - `upsert_budget(conn, user_id, category, amount, period, budget_type)` — updated signature
  - `get_discretionary_total(conn, user_id, year, month) -> tuple[float, float]` — returns `(spent, budget)`
  - `get_next_milestone(conn, user_id) -> dict | None` — returns next upcoming milestone

- [ ] **Step 1: Update `upsert_budget` signature in db.py**

In `backend/domains/finance/db.py`, update `upsert_budget`:

```python
def upsert_budget(conn: sqlite3.Connection, user_id: int, category: str,
                  amount: float, period: str = "monthly",
                  budget_type: str = "discretionary") -> int:
    from datetime import date
    category = category.lower().strip()
    conn.execute(
        """INSERT INTO budgets(user_id, category, amount, period, budget_type, start_date)
           VALUES (?,?,?,?,?,?)
           ON CONFLICT(user_id, category, period) DO UPDATE SET
             amount=excluded.amount,
             budget_type=excluded.budget_type,
             start_date=excluded.start_date""",
        (user_id, category, amount, period, budget_type, date.today().isoformat())
    )
    conn.commit()
    row = conn.execute(
        "SELECT id FROM budgets WHERE user_id=? AND category=? AND period=?",
        (user_id, category, period)
    ).fetchone()
    return row["id"]
```

- [ ] **Step 2: Add `get_discretionary_total` to db.py**

```python
def get_discretionary_total(conn: sqlite3.Connection, user_id: int,
                             year: int, month: int) -> tuple[float, float]:
    """Returns (spent, budget) for discretionary categories only."""
    month_str = f"{year:04d}-{month:02d}"
    disc_cats = [r["category"] for r in conn.execute(
        "SELECT category FROM budgets WHERE user_id=? AND budget_type='discretionary'",
        (user_id,)
    ).fetchall()]
    if not disc_cats:
        return 0.0, 0.0
    placeholders = ",".join("?" * len(disc_cats))
    spent_row = conn.execute(
        f"""SELECT COALESCE(ABS(SUM(amount)), 0) as total
            FROM transactions
            WHERE user_id=? AND strftime('%Y-%m', date)=?
              AND amount < 0 AND category IN ({placeholders})""",
        [user_id, month_str] + disc_cats
    ).fetchone()
    budget_row = conn.execute(
        f"SELECT COALESCE(SUM(amount), 0) as total FROM budgets WHERE user_id=? AND budget_type='discretionary'",
        (user_id,)
    ).fetchone()
    return round(spent_row["total"], 2), round(budget_row["total"], 2)
```

- [ ] **Step 3: Add `get_next_milestone` to db.py**

```python
def get_next_milestone(conn: sqlite3.Connection, user_id: int) -> dict | None:
    """Returns the next upcoming milestone (target_date >= today)."""
    from datetime import date
    today = date.today().isoformat()
    row = conn.execute(
        """SELECT * FROM financial_milestones
           WHERE user_id=? AND target_date >= ?
           ORDER BY target_date ASC LIMIT 1""",
        (user_id, today)
    ).fetchone()
    return dict(row) if row else None
```

- [ ] **Step 4: Update `budget_summary` router endpoint**

In `backend/domains/finance/router.py`:

Add imports at top of file alongside existing db imports:
```python
from domains.finance.db import (
    ...  # existing imports
    get_discretionary_total,
    get_next_milestone,
)
```

Update `BudgetCreate` model:
```python
class BudgetCreate(BaseModel):
    user_id: int = 1
    category: str
    amount: float
    period: str = "monthly"
    budget_type: str = "discretionary"
```

Replace the `budget_summary` endpoint body. The key change is: group categories by `budget_type`, compute per-type totals, add `discretionary_spent`/`discretionary_budget`, add `next_milestone`:

```python
EXCLUDED_FROM_TOTAL = {"income", "savings"}

@router.get("/summary/{year}/{month}")
def budget_summary(year: int, month: int, user_id: int = 1):
    if not (1 <= month <= 12):
        raise HTTPException(400, "month must be 1–12")
    conn = _conn()
    try:
        spend = get_monthly_spend(conn, user_id, year, month)
        budgets = list_budgets(conn, user_id)
        disc_spent, disc_budget = get_discretionary_total(conn, user_id, year, month)
        next_ms = get_next_milestone(conn, user_id)

        # Build budget map including type info
        budget_map: dict[str, dict] = {
            b["category"]: b for b in budgets
        }

        # Per-type grouping
        by_type: dict[str, list] = {
            "fixed": [], "recurring": [], "discretionary": [], "envelope": []
        }

        all_cats = sorted(set(list(spend.keys()) + list(budget_map.keys())))
        categories = []
        for cat in all_cats:
            spent = spend.get(cat, 0.0)
            b = budget_map.get(cat)
            limit = b["amount"] if b else None
            btype = b["budget_type"] if b else "discretionary"
            period = b["period"] if b else "monthly"
            is_excluded = cat.lower() in EXCLUDED_FROM_TOTAL
            entry = {
                "category": cat,
                "spent": round(spent, 2),
                "budget": round(limit, 2) if limit is not None else None,
                "budget_type": btype,
                "period": period,
                "over_budget": limit is not None and spent > limit and not is_excluded,
                "is_excluded": is_excluded,
            }
            categories.append(entry)
            if btype in by_type and not is_excluded:
                by_type[btype].append(entry)

        total_spent = sum(v for k, v in spend.items() if k.lower() not in EXCLUDED_FROM_TOTAL)
        total_budget = sum(
            b["amount"] for b in budgets
            if b["category"].lower() not in EXCLUDED_FROM_TOTAL
            and b["budget_type"] != "envelope"
            and b["period"] == "monthly"
        ) or None

        return {
            "year": year,
            "month": month,
            "total_spent": round(total_spent, 2),
            "total_budget": round(total_budget, 2) if total_budget else None,
            "discretionary_spent": disc_spent,
            "discretionary_budget": disc_budget,
            "next_milestone": next_ms,
            "categories": categories,
            "by_type": by_type,
        }
    finally:
        conn.close()
```

- [ ] **Step 5: Update `create_budget` endpoint to pass budget_type**

```python
@router.post("/budgets")
def create_budget(body: BudgetCreate):
    conn = _conn()
    try:
        body.category = body.category.lower().strip()
        bid = upsert_budget(conn, body.user_id, body.category,
                            body.amount, body.period, body.budget_type)
        return {"id": bid, "category": body.category,
                "amount": body.amount, "period": body.period,
                "budget_type": body.budget_type}
    finally:
        conn.close()
```

- [ ] **Step 6: Restart backend and verify**

```bash
kill $(ps aux | grep "python3 backend/main.py" | grep -v grep | awk '{print $2}') 2>/dev/null
sleep 1
cd /Users/me/deep-workspace/chitiyu-pi && uv run python backend/main.py &
sleep 3
curl -s "http://localhost:8000/finance/summary/2026/8" -H "x-api-key: chitiyu-2026" | python3 -c "
import sys,json
d=json.load(sys.stdin)
print('discretionary_spent:', d['discretionary_spent'])
print('discretionary_budget:', d['discretionary_budget'])
print('next_milestone:', d['next_milestone'])
print('by_type keys:', list(d['by_type'].keys()))
for btype, cats in d['by_type'].items():
    print(f'  {btype}: {[c[\"category\"] for c in cats]}')
"
```

Expected: `discretionary_budget: 800.0` (groceries+dining+shopping+misc+fuel), `by_type` has 4 keys, envelopes listed correctly.

---

## Task 3: Frontend — update TypeScript interfaces

**Files:**
- Modify: `app/lib/api.ts`

**Interfaces:**
- Consumes: new backend summary response shape from Task 2
- Produces: updated `CategoryBudget`, `FinanceSummary`, `Budget` types; new `setBudgetWithType` function

- [ ] **Step 1: Update `CategoryBudget` interface**

```typescript
export interface CategoryBudget {
  category: string;
  spent: number;
  budget: number | null;
  budget_type: "fixed" | "recurring" | "discretionary" | "envelope";
  period: "monthly" | "biannual" | "annual" | "weekly";
  over_budget: boolean;
  is_excluded: boolean;
}
```

- [ ] **Step 2: Update `FinanceSummary` interface**

```typescript
export interface Milestone {
  id: number;
  period_label: string;
  target_date: string;
  expected_net_worth: number;
  actual_net_worth: number | null;
  note: string | null;
}

export interface FinanceSummary {
  year: number;
  month: number;
  total_spent: number;
  total_budget: number | null;
  discretionary_spent: number;
  discretionary_budget: number;
  next_milestone: Milestone | null;
  categories: CategoryBudget[];
  by_type: {
    fixed: CategoryBudget[];
    recurring: CategoryBudget[];
    discretionary: CategoryBudget[];
    envelope: CategoryBudget[];
  };
}
```

- [ ] **Step 3: Update `Budget` interface and add `setBudgetWithType`**

```typescript
export interface Budget {
  id: number;
  category: string;
  amount: number;
  period: "monthly" | "biannual" | "annual" | "weekly";
  budget_type: "fixed" | "recurring" | "discretionary" | "envelope";
}

export const setBudget = (category: string, amount: number) =>
  request<Budget>("POST", "/finance/budgets", { category, amount });

export const setBudgetWithType = (
  category: string,
  amount: number,
  budget_type: Budget["budget_type"],
  period: Budget["period"] = "monthly"
) =>
  request<Budget>("POST", "/finance/budgets", { category, amount, budget_type, period });
```

---

## Task 4: Frontend — smart hero card

**Files:**
- Modify: `app/app/(tabs)/finance.tsx`

**Interfaces:**
- Consumes: `FinanceSummary` with `discretionary_spent`, `discretionary_budget`, `next_milestone`, `by_type`

The hero becomes a single card with two parts:
1. **Top**: discretionary spend progress (amount spent, amount left, progress bar, %)
2. **Bottom**: next milestone — one sentence: "Chase target Aug 14: $14,369 — you need $2,455 more" or "You're $430 ahead of Aug 28 target ✓"

- [ ] **Step 1: Replace hero JSX in finance.tsx**

Find the existing hero block (starts with `{/* ── HERO: Monthly Budget`). Replace entirely:

```tsx
{/* ── HERO ───────────────────────────────────────────────────── */}
{summary && (
  <View style={[s.hero, { backgroundColor: colors.card }]}>
    {/* Part 1: Discretionary spend */}
    <Text style={[s.heroLabel, { color: colors.textSecondary }]}>
      DISCRETIONARY — {monthName.toUpperCase()}
    </Text>
    <View style={s.heroRow}>
      <View>
        <Text style={[s.heroAmount, { color: colors.text }]}>
          {fmt(summary.discretionary_spent)}
        </Text>
        <Text style={[s.heroSub, { color: colors.textSecondary }]}>
          {summary.discretionary_budget > 0
            ? `spent of ${fmt(summary.discretionary_budget)}`
            : "spent"}
        </Text>
      </View>
      {summary.discretionary_budget > 0 && (
        <View style={s.heroRight}>
          <Text style={[s.heroPct, {
            color: summary.discretionary_spent > summary.discretionary_budget
              ? colors.accentRed : colors.accentGreen,
          }]}>
            {Math.round((summary.discretionary_spent / summary.discretionary_budget) * 100)}%
          </Text>
          <Text style={[s.heroSub, { color: colors.textSecondary }]}>used</Text>
        </View>
      )}
    </View>
    {summary.discretionary_budget > 0 && (
      <View style={s.heroBar}>
        <View style={[s.heroBarBg, { backgroundColor: colors.border }]}>
          <View style={[s.heroBarFill, {
            backgroundColor: summary.discretionary_spent > summary.discretionary_budget
              ? colors.accentRed : colors.accentGreen,
            width: `${Math.min((summary.discretionary_spent / summary.discretionary_budget) * 100, 100)}%` as any,
          }]} />
        </View>
        <Text style={[s.heroRemaining, { color: colors.textSecondary }]}>
          {summary.discretionary_spent <= summary.discretionary_budget
            ? `${fmt(summary.discretionary_budget - summary.discretionary_spent)} left to spend freely`
            : `${fmt(summary.discretionary_spent - summary.discretionary_budget)} over discretionary budget`}
        </Text>
      </View>
    )}

    {/* Divider */}
    {summary.next_milestone && (
      <View style={[s.heroDivider, { backgroundColor: colors.border }]} />
    )}

    {/* Part 2: Next milestone */}
    {summary.next_milestone && (() => {
      const ms = summary.next_milestone!;
      const dateLabel = new Date(ms.target_date + "T00:00:00").toLocaleDateString("en-US", {
        month: "short", day: "numeric",
      });
      const target = ms.expected_net_worth;
      // We compare Chase checking balance to target — user enters actual via milestone PATCH
      const actual = ms.actual_net_worth;
      const hasActual = actual != null;
      const ahead = hasActual && actual >= target;
      return (
        <View style={s.heroMilestone}>
          <Text style={[s.heroMilestoneLabel, { color: colors.textSecondary }]}>
            SAVINGS TARGET · {dateLabel}
          </Text>
          <Text style={[s.heroMilestoneValue, {
            color: hasActual ? (ahead ? colors.accentGreen : colors.accentRed) : colors.text,
          }]}>
            {hasActual
              ? ahead
                ? `${fmt(actual - target)} ahead of ${fmt(target)} ✓`
                : `${fmt(target - actual)} short of ${fmt(target)}`
              : `Target: ${fmt(target)}`}
          </Text>
        </View>
      );
    })()}
  </View>
)}
```

- [ ] **Step 2: Add hero styles**

In the StyleSheet, update/add hero styles:

```typescript
hero: { borderRadius: 12, padding: 20, marginBottom: 12 },
heroLabel: { fontSize: 11, fontWeight: "600", letterSpacing: 1, marginBottom: 8 },
heroRow: { flexDirection: "row", justifyContent: "space-between", alignItems: "flex-end", marginBottom: 16 },
heroAmount: { fontSize: 34, fontWeight: "700" },
heroSub: { fontSize: 13, marginTop: 2 },
heroRight: { alignItems: "flex-end" },
heroPct: { fontSize: 28, fontWeight: "700" },
heroBar: { gap: 6 },
heroBarBg: { height: 6, borderRadius: 3, overflow: "hidden" },
heroBarFill: { height: 6, borderRadius: 3 },
heroRemaining: { fontSize: 12 },
heroDivider: { height: StyleSheet.hairlineWidth, marginVertical: 16 },
heroMilestone: { gap: 4 },
heroMilestoneLabel: { fontSize: 11, fontWeight: "600", letterSpacing: 0.8 },
heroMilestoneValue: { fontSize: 14, fontWeight: "600" },
```

---

## Task 5: Frontend — restructure accordion sections by budget_type

**Files:**
- Modify: `app/app/(tabs)/finance.tsx`

**Interfaces:**
- Consumes: `summary.by_type` — `{ fixed, recurring, discretionary, envelope }` each an array of `CategoryBudget`
- Consumes: `setBudgetWithType` from `app/lib/api.ts`

Replace the single "August Budget" accordion with four typed sections. Also update the budget edit modal to expose `budget_type` and `period` fields when adding a new budget.

- [ ] **Step 1: Replace the budget accordion section**

Find the `{/* ── THIS MONTH ──`} block. Replace with four accordions:

```tsx
{/* ── DISCRETIONARY ──────────────────────────────────────────── */}
<Accordion
  title="Discretionary"
  badge={summary ? `${fmt(summary.discretionary_spent)} spent` : undefined}
  defaultOpen
>
  {summary && summary.by_type.discretionary.length === 0 && (
    <Text style={[s.emptyHint, { color: colors.textSecondary }]}>
      No discretionary budgets set.
    </Text>
  )}
  {summary && summary.by_type.discretionary.map((cat) => (
    <TouchableOpacity
      key={cat.category}
      style={[s.catRow, { borderBottomColor: colors.border }]}
      onPress={() => openBudgetEdit(cat.category)}
    >
      <Text style={[s.catName, { color: colors.text }]}>
        {cat.category.charAt(0).toUpperCase() + cat.category.slice(1)}
      </Text>
      <View style={s.catRight}>
        <Text style={[s.catAmount, { color: cat.over_budget ? colors.accentRed : colors.text }]}>
          {fmt(cat.spent)}
          {cat.budget != null && (
            <Text style={{ color: colors.textSecondary, fontWeight: "400" }}>
              {" "}/ {fmt(cat.budget)}
            </Text>
          )}
        </Text>
        {cat.over_budget && (
          <View style={[s.overTag, { backgroundColor: colors.accentRed + "22" }]}>
            <Text style={[s.overTagText, { color: colors.accentRed }]}>OVER</Text>
          </View>
        )}
        <Text style={{ color: colors.textTertiary, fontSize: 12 }}>›</Text>
      </View>
    </TouchableOpacity>
  ))}
  <TouchableOpacity
    style={[s.updateBtn, { borderColor: colors.accent, marginTop: 8 }]}
    onPress={() => openBudgetEdit("")}
  >
    <Text style={[s.updateBtnText, { color: colors.accent }]}>+ Add Budget</Text>
  </TouchableOpacity>
</Accordion>

{/* ── ENVELOPES (6-month pools) ────────────────────────────────── */}
{summary && summary.by_type.envelope.length > 0 && (
  <Accordion title="Envelopes (6-month)" defaultOpen={false}
    badge={(() => {
      const totalBudget = summary.by_type.envelope.reduce((s, c) => s + (c.budget ?? 0), 0);
      const totalSpent = summary.by_type.envelope.reduce((s, c) => s + c.spent, 0);
      return totalBudget > 0 ? `${fmt(totalBudget - totalSpent)} left` : undefined;
    })()}
  >
    {summary.by_type.envelope.map((cat) => (
      <TouchableOpacity
        key={cat.category}
        style={[s.catRow, { borderBottomColor: colors.border }]}
        onPress={() => openBudgetEdit(cat.category)}
      >
        <View style={{ flex: 1 }}>
          <Text style={[s.catName, { color: colors.text }]}>
            {cat.category.charAt(0).toUpperCase() + cat.category.slice(1)}
          </Text>
          <Text style={{ fontSize: 11, color: colors.textTertiary, marginTop: 1 }}>6-month pool</Text>
        </View>
        <View style={s.catRight}>
          <Text style={[s.catAmount, { color: cat.over_budget ? colors.accentRed : colors.text }]}>
            {fmt(cat.spent)}
            {cat.budget != null && (
              <Text style={{ color: colors.textSecondary, fontWeight: "400" }}>
                {" "}/ {fmt(cat.budget)}
              </Text>
            )}
          </Text>
          {cat.over_budget && (
            <View style={[s.overTag, { backgroundColor: colors.accentRed + "22" }]}>
              <Text style={[s.overTagText, { color: colors.accentRed }]}>OVER</Text>
            </View>
          )}
          <Text style={{ color: colors.textTertiary, fontSize: 12 }}>›</Text>
        </View>
      </TouchableOpacity>
    ))}
  </Accordion>
)}

{/* ── FIXED ───────────────────────────────────────────────────── */}
{summary && summary.by_type.fixed.length > 0 && (
  <Accordion title="Fixed" defaultOpen={false}
    badge={summary.by_type.fixed.reduce((s, c) => s + (c.budget ?? 0), 0) > 0
      ? fmt(summary.by_type.fixed.reduce((s, c) => s + (c.budget ?? 0), 0))
      : undefined}
  >
    {summary.by_type.fixed.map((cat) => (
      <TouchableOpacity
        key={cat.category}
        style={[s.catRow, { borderBottomColor: colors.border }]}
        onPress={() => openBudgetEdit(cat.category)}
      >
        <Text style={[s.catName, { color: colors.text }]}>
          {cat.category.charAt(0).toUpperCase() + cat.category.slice(1)}
        </Text>
        <Text style={[s.catAmount, { color: colors.textSecondary }]}>
          {cat.budget != null ? fmt(cat.budget) : "—"}/mo
        </Text>
      </TouchableOpacity>
    ))}
  </Accordion>
)}

{/* ── RECURRING ───────────────────────────────────────────────── */}
{summary && summary.by_type.recurring.filter(c => !c.is_excluded).length > 0 && (
  <Accordion title="Recurring" defaultOpen={false}>
    {summary.by_type.recurring.filter(c => !c.is_excluded).map((cat) => (
      <TouchableOpacity
        key={cat.category}
        style={[s.catRow, { borderBottomColor: colors.border }]}
        onPress={() => openBudgetEdit(cat.category)}
      >
        <Text style={[s.catName, { color: colors.text }]}>
          {cat.category.charAt(0).toUpperCase() + cat.category.slice(1)}
        </Text>
        <Text style={[s.catAmount, { color: colors.textSecondary }]}>
          {cat.budget != null ? fmt(cat.budget) : "—"}/mo
        </Text>
      </TouchableOpacity>
    ))}
  </Accordion>
)}
```

- [ ] **Step 2: Update budget modal to support budget_type and period**

Add state:
```typescript
const [editingBudgetType, setEditingBudgetType] = useState<Budget["budget_type"]>("discretionary");
const [editingPeriod, setEditingPeriod] = useState<Budget["period"]>("monthly");
```

Update `openBudgetEdit` to set these from the existing category data:
```typescript
const openBudgetEdit = (category: string) => {
  const catData = summary?.categories.find(
    (c) => c.category.toLowerCase() === category.toLowerCase()
  );
  setBudgetInput(catData?.budget != null ? String(catData.budget) : "");
  setEditingSpend(catData?.spent ?? null);
  setEditingBudgetType(catData?.budget_type ?? "discretionary");
  setEditingPeriod(catData?.period ?? "monthly");
  setEditingCategory(category);
  setNewCategoryInput("");
  setBudgetModalVisible(true);
};
```

Update `handleSaveBudget` to call `setBudgetWithType`:
```typescript
const handleSaveBudget = async () => {
  const targetCategory = editingCategory || newCategoryInput.trim();
  if (!targetCategory) { Alert.alert("Missing category", "Enter a category name."); return; }
  const amount = parseFloat(budgetInput);
  if (isNaN(amount) || amount <= 0) { Alert.alert("Invalid amount", "Enter a positive number."); return; }
  setSavingBudget(true);
  try {
    await setBudgetWithType(targetCategory, amount, editingBudgetType, editingPeriod);
    await loadData();
    setBudgetModalVisible(false);
  } catch (e: any) {
    Alert.alert("Couldn't save budget", e?.message ?? "Please try again.");
  } finally {
    setSavingBudget(false);
  }
};
```

In the budget modal JSX, add type + period pickers when `!editingCategory` (new budget) OR always show when editing (so user can reclassify):

```tsx
{/* Budget type picker */}
<Text style={[s.pickerLabel, { color: colors.textSecondary }]}>Type</Text>
<ScrollView horizontal showsHorizontalScrollIndicator={false} style={{ marginBottom: 12 }}>
  <View style={s.pillRow}>
    {(["discretionary","fixed","recurring","envelope"] as Budget["budget_type"][]).map((t) => (
      <TouchableOpacity
        key={t}
        style={[s.pill, { backgroundColor: editingBudgetType === t ? colors.accent : colors.cardElevated }]}
        onPress={() => {
          setEditingBudgetType(t);
          if (t === "envelope") setEditingPeriod("biannual");
          else setEditingPeriod("monthly");
        }}
      >
        <Text style={[s.pillText, { color: editingBudgetType === t ? "#fff" : colors.textSecondary }]}>{t}</Text>
      </TouchableOpacity>
    ))}
  </View>
</ScrollView>

{/* Period — only show for envelope */}
{editingBudgetType === "envelope" && (
  <>
    <Text style={[s.pickerLabel, { color: colors.textSecondary }]}>Period</Text>
    <ScrollView horizontal showsHorizontalScrollIndicator={false} style={{ marginBottom: 12 }}>
      <View style={s.pillRow}>
        {(["monthly","biannual","annual"] as Budget["period"][]).map((p) => (
          <TouchableOpacity
            key={p}
            style={[s.pill, { backgroundColor: editingPeriod === p ? colors.accent : colors.cardElevated }]}
            onPress={() => setEditingPeriod(p)}
          >
            <Text style={[s.pillText, { color: editingPeriod === p ? "#fff" : colors.textSecondary }]}>{p}</Text>
          </TouchableOpacity>
        ))}
      </View>
    </ScrollView>
  </>
)}
```

---

## Task 6: Seed corrected envelope budgets and verify end-to-end

**Files:**
- No code changes — data seeding + verification only

The migration script in Task 1 handles seeding. This task verifies everything is correct end-to-end.

- [ ] **Step 1: Verify budget summary response**

```bash
curl -s "http://localhost:8000/finance/summary/2026/8" -H "x-api-key: chitiyu-2026" | python3 -c "
import sys,json
d=json.load(sys.stdin)
print('=== Hero numbers ===')
print(f'discretionary_spent:  \${d[\"discretionary_spent\"]:,.2f}')
print(f'discretionary_budget: \${d[\"discretionary_budget\"]:,.2f}')
print(f'next_milestone: {d[\"next_milestone\"]}')
print()
print('=== By type ===')
for btype, cats in d['by_type'].items():
    total = sum(c['budget'] or 0 for c in cats)
    print(f'{btype:15s}: {[c[\"category\"] for c in cats]}  total=\${total:,.2f}')
"
```

Expected:
- `discretionary_budget: 800.0` (groceries $200 + dining $150 + shopping $150 + misc $200 + fuel $100)
- `by_type.envelope` contains travel, insurance, gifts with biannual period
- `by_type.fixed` contains mortgage, car, utilities, subscriptions
- `by_type.recurring` contains family

- [ ] **Step 2: Verify envelope amounts in DB**

```bash
cd /Users/me/deep-workspace/chitiyu-pi && .venv/bin/python3 -c "
import sqlite3
conn = sqlite3.connect('chitiyu.db')
rows = conn.execute(\"SELECT category, amount, period, budget_type FROM budgets WHERE budget_type='envelope'\").fetchall()
for r in rows: print(r)
"
```

Expected: travel=10000/biannual, insurance=2500/biannual, gifts=1500/biannual

- [ ] **Step 3: Manual smoke test in app**

Open the Finance tab. Verify:
1. Hero shows "DISCRETIONARY — AUGUST" with ~$800 budget
2. Hero bottom shows next milestone date and target amount
3. Discretionary accordion is open with 5 categories
4. Envelopes accordion shows travel/insurance/gifts with "6-month pool" subtitle
5. Fixed accordion shows mortgage/car/utilities/subscriptions
6. Tapping a category opens budget modal with correct type pre-selected
7. Changing type to "envelope" auto-sets period to "biannual"
