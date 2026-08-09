# Expo App UX Gaps Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix all UX gaps across 5 tabs of the Chitiyu PI Expo app — collapsed insight cards, meal sections, calorie confirmation, recipe quick-select, swipe-to-delete on meals/transactions, budget editing, category picker, and a full dark/light theme system.

**Architecture:** Backend gets 3 new endpoints (meal preview, meal from-recipe, delete meal) + 2 new delete endpoints for transactions. Frontend gets a shared theme system replacing all hardcoded colors, plus new interaction patterns (expand/collapse, swipe delete, multi-step sheets) consistent with the existing PanResponder swipe pattern already in TaskRow.tsx.

**Tech Stack:** React Native 0.81.5, Expo SDK 54, expo-router 6, FastAPI/Python backend, SQLite via sqlite3, Claude Haiku for NL parsing (DISPATCH_MODEL).

## Global Constraints

- No new npm packages — use only React Native built-ins (`Animated`, `PanResponder`, `useColorScheme`) already available in SDK 54
- No new pip packages — backend uses only stdlib + existing deps
- All backend endpoints follow the existing pattern: `_conn()`, `try/finally conn.close()`, `Depends(verify_api_key)`
- Backend user_id defaults to 1 (single-user app)
- Swipe-to-delete uses the PanResponder pattern from `app/components/TaskRow.tsx` — copy exactly, don't reinvent
- Theme system uses `useColorScheme` from `react-native` — no third-party theming lib
- All tests run via `pytest` from `~/deep-workspace/chitiyu-pi/`
- API base URL: `http://10.0.0.179:8000`, API key header: `X-Api-Key: chitiyu-2026`

---

## File Map

**New files:**
- `app/lib/theme.ts` — color tokens for dark/light, `useTheme()` hook
- `app/components/MealRow.tsx` — swipeable meal row with delete

**Modified backend files:**
- `backend/domains/health/db.py` — add `delete_meal()`
- `backend/domains/health/router.py` — add `/meals/preview`, `/meals/from-recipe`, `DELETE /meals/{id}`
- `backend/domains/finance/db.py` — add `delete_transaction()`
- `backend/domains/finance/router.py` — add `DELETE /transactions/{id}`

**Modified frontend files:**
- `app/lib/api.ts` — add: `deleteMeal`, `getMealPreview`, `logMealFromRecipe`, `getRecipes`, `createRecipe`, `deleteTransaction`, `getBudgets`, `setBudget`, `logExpense` (add category param)
- `app/components/InsightCard.tsx` — expand/collapse + dismiss
- `app/components/TransactionRow.tsx` — add swipe-to-delete
- `app/app/(tabs)/index.tsx` — wire dismiss state
- `app/app/(tabs)/health.tsx` — meal sections, confirmation flow, recipe quick-select, use MealRow
- `app/app/(tabs)/finance.tsx` — delete wiring, budget edit section, category picker
- `app/app/(tabs)/tasks.tsx` — theme colors only
- `app/app/(tabs)/knowledge.tsx` — theme colors only
- `app/app/_layout.tsx` — theme colors on tab bar

---

### Task 1: Backend — Delete Meal + Delete Transaction endpoints

**Files:**
- Modify: `backend/domains/health/db.py`
- Modify: `backend/domains/health/router.py`
- Modify: `backend/domains/finance/db.py`
- Modify: `backend/domains/finance/router.py`
- Test: `tests/test_api_health.py` (add cases)
- Test: `tests/test_finance_db.py` (add cases)

**Interfaces:**
- Produces: `DELETE /health/meals/{meal_id}` → `{"ok": true}` or 404
- Produces: `DELETE /finance/transactions/{tx_id}` → `{"ok": true}` or 404

- [ ] **Step 1: Add `delete_meal` to health/db.py**

Open `backend/domains/health/db.py`. Add after `insert_recipe`:

```python
def delete_meal(conn: sqlite3.Connection, user_id: int, meal_id: int) -> bool:
    cur = conn.execute(
        "DELETE FROM meals WHERE id=? AND user_id=?", (meal_id, user_id)
    )
    conn.commit()
    return cur.rowcount > 0
```

- [ ] **Step 2: Add DELETE /health/meals/{meal_id} to health/router.py**

In `backend/domains/health/router.py`, add the import and endpoint:

```python
# Add to imports at top:
from domains.health.db import (get_today_meals, get_meals_for_date, get_metrics_for_date,
                               upsert_health_metrics, insert_recipe, get_all_recipes, delete_meal)

# Add new endpoint after the /recipes POST:
@router.delete("/meals/{meal_id}")
def delete_meal_endpoint(meal_id: int, user_id: int = 1):
    conn = _conn()
    ok = delete_meal(conn, user_id, meal_id)
    conn.close()
    if not ok:
        raise HTTPException(404, "Meal not found")
    return {"ok": True}
```

- [ ] **Step 3: Add `delete_transaction` to finance/db.py**

Open `backend/domains/finance/db.py`. Add after `list_transactions`:

```python
def delete_transaction(conn: sqlite3.Connection, user_id: int, tx_id: int) -> bool:
    cur = conn.execute(
        "DELETE FROM transactions WHERE id=? AND user_id=?", (tx_id, user_id)
    )
    conn.commit()
    return cur.rowcount > 0
```

- [ ] **Step 4: Add DELETE /finance/transactions/{tx_id} to finance/router.py**

In `backend/domains/finance/router.py`, add import and endpoint:

```python
# Add delete_transaction to the existing import from domains.finance.db:
from domains.finance.db import (
    insert_account, get_account_by_name, list_accounts,
    insert_transaction, list_transactions, delete_transaction,
    get_monthly_spend, get_category_spend_this_month,
    upsert_budget, list_budgets, get_budget,
    insert_net_worth, get_latest_net_worth, list_net_worth_snapshots,
    insert_savings_goal, update_savings_goal_progress, list_savings_goals, get_savings_goal,
)

# Add after the GET /transactions endpoint:
@router.delete("/transactions/{tx_id}")
def delete_transaction_endpoint(tx_id: int, user_id: int = 1):
    conn = _conn()
    ok = delete_transaction(conn, user_id, tx_id)
    conn.close()
    if not ok:
        raise HTTPException(404, "Transaction not found")
    return {"ok": True}
```

- [ ] **Step 5: Write tests**

Add to `tests/test_api_health.py` (find the existing test file and append):

```python
def test_delete_meal(client, sample_user):
    # First log a meal to get an id
    r = client.post("/health/meals", json={"text": "1 banana"})
    # Get today's meals to find the id
    r2 = client.get("/health/meals/today")
    meals = r2.json()["meals"]
    assert len(meals) > 0
    meal_id = meals[-1]["id"]
    # Delete it
    r3 = client.delete(f"/health/meals/{meal_id}")
    assert r3.status_code == 200
    assert r3.json()["ok"] is True
    # Verify gone
    r4 = client.get("/health/meals/today")
    ids = [m["id"] for m in r4.json()["meals"]]
    assert meal_id not in ids

def test_delete_meal_not_found(client):
    r = client.delete("/health/meals/99999")
    assert r.status_code == 404
```

Add to `tests/test_finance_db.py`:

```python
def test_delete_transaction(tmp_db):
    conn = get_connection(tmp_db)
    initialize_schema(conn)
    tid = insert_transaction(conn, 1, "2026-08-07", -50.0, "food", "lunch", "manual")
    assert delete_transaction(conn, 1, tid) is True
    rows = list_transactions(conn, 1)
    assert all(r["id"] != tid for r in rows)

def test_delete_transaction_wrong_user(tmp_db):
    conn = get_connection(tmp_db)
    initialize_schema(conn)
    tid = insert_transaction(conn, 1, "2026-08-07", -50.0, "food", "lunch", "manual")
    assert delete_transaction(conn, 2, tid) is False  # wrong user_id
```

- [ ] **Step 6: Run tests**

```bash
cd ~/deep-workspace/chitiyu-pi && python -m pytest tests/test_api_health.py tests/test_finance_db.py -v -x 2>&1 | tail -30
```

Expected: all pass (or pre-existing tests pass + new ones pass).

- [ ] **Step 7: Commit**

```bash
cd ~/deep-workspace/chitiyu-pi
git add backend/domains/health/db.py backend/domains/health/router.py \
        backend/domains/finance/db.py backend/domains/finance/router.py \
        tests/test_api_health.py tests/test_finance_db.py
git commit -m "feat(backend): add delete meal and delete transaction endpoints"
```

---

### Task 2: Backend — Meal Preview + Log From Recipe endpoints

**Files:**
- Modify: `backend/domains/health/router.py`
- Modify: `backend/domains/health/db.py`
- Test: `tests/test_api_health.py`

**Interfaces:**
- Consumes: existing `log_meal` tool pattern from `health/tools.py`
- Produces: `POST /health/meals/preview` body `{text, context?}` → `{description, calories, protein, fat, carbs}`
- Produces: `POST /health/meals/from-recipe` body `{recipe_id, user_id?}` → `{"result": str}`

- [ ] **Step 1: Add `parse_meal_macros` helper to health/tools.py**

Open `backend/domains/health/tools.py`. Add a new function that does the LLM call + JSON parse but does NOT insert:

```python
def parse_meal_macros(text: str, context: str = "") -> dict | None:
    """Call Claude to parse meal text into macros. Returns dict or None on failure."""
    raw = call_claude(_PARSE_PROMPT.format(text=text, context=context),
                      model=DISPATCH_MODEL, timeout=20)
    m = re.search(r'\{.*\}', raw, re.DOTALL)
    if not m:
        return None
    return json.loads(m.group())
```

Also refactor `log_meal` to use it:

```python
def log_meal(conn: sqlite3.Connection, user_id: int, text: str, context: str = "") -> str:
    data = parse_meal_macros(text, context)
    if data is None:
        return "Couldn't parse that meal. Try: '2 eggs, toast, coffee'."
    insert_meal(conn, user_id, data["description"], data["calories"],
                data["protein"], data.get("fat"), data.get("carbs"))
    result = format_meal_confirmation(data["description"], data["calories"], data["protein"])
    try:
        from orchestrator.insights import trigger_insights_async
        trigger_insights_async(user_id, scope="today")
    except Exception:
        pass
    return result
```

- [ ] **Step 2: Add `log_meal_from_recipe` to health/db.py**

```python
def log_meal_from_recipe(conn: sqlite3.Connection, user_id: int, recipe_id: int) -> dict | None:
    """Fetch recipe and insert a meal row. Returns the meal dict or None if recipe not found."""
    row = conn.execute(
        "SELECT * FROM recipes WHERE id=? AND user_id=?", (recipe_id, user_id)
    ).fetchone()
    if not row:
        return None
    recipe = dict(row)
    from datetime import datetime, timezone
    conn.execute(
        "INSERT INTO meals(user_id, description, calories, protein, fat, carbs, source, recipe_id) "
        "VALUES (?,?,?,?,?,?,?,?)",
        (user_id, recipe["name"], recipe["calories"], recipe["protein"],
         recipe.get("fat"), recipe.get("carbs"), "recipe", recipe_id)
    )
    conn.commit()
    return recipe
```

- [ ] **Step 3: Add the two new endpoints to health/router.py**

Add `parse_meal_macros` to the tools import and add two endpoints:

```python
# In the log_meal_endpoint, also import parse_meal_macros:
# (It's imported inline — add as a module-level import instead)

class MealPreview(BaseModel):
    user_id: int = 1
    text: str
    context: str = ""

class MealFromRecipe(BaseModel):
    user_id: int = 1
    recipe_id: int

@router.post("/meals/preview")
def preview_meal(body: MealPreview):
    from domains.health.tools import parse_meal_macros
    data = parse_meal_macros(body.text, body.context)
    if data is None:
        raise HTTPException(422, "Couldn't parse that meal. Try: '2 eggs, toast, coffee'.")
    return data

@router.post("/meals/from-recipe")
def log_from_recipe(body: MealFromRecipe):
    from domains.health.db import log_meal_from_recipe
    conn = _conn()
    recipe = log_meal_from_recipe(conn, body.user_id, body.recipe_id)
    conn.close()
    if recipe is None:
        raise HTTPException(404, "Recipe not found")
    try:
        from orchestrator.insights import trigger_insights_async
        trigger_insights_async(body.user_id, scope="today")
    except Exception:
        pass
    return {"result": f"Logged {recipe['name']} — {recipe['calories']} kcal"}
```

**IMPORTANT:** `/meals/preview` and `/meals/from-recipe` must be defined BEFORE `/meals/{date}` in the router file, otherwise FastAPI will try to match "preview" and "from-recipe" as date path params. Check the existing order and insert above `/meals/{date}`.

- [ ] **Step 4: Write tests**

Add to `tests/test_api_health.py`:

```python
def test_preview_meal(client):
    r = client.post("/health/meals/preview", json={"text": "oatmeal with berries"})
    assert r.status_code == 200
    data = r.json()
    assert "calories" in data
    assert "protein" in data
    assert isinstance(data["calories"], (int, float))

def test_preview_meal_returns_no_db_row(client):
    before = client.get("/health/meals/today").json()["meals"]
    client.post("/health/meals/preview", json={"text": "oatmeal"})
    after = client.get("/health/meals/today").json()["meals"]
    assert len(before) == len(after)  # preview must not insert

def test_log_from_recipe(client):
    # Create a recipe first
    r = client.post("/health/recipes", json={
        "name": "Test Oats", "calories": 300, "protein": 10.0, "fat": 5.0, "carbs": 50.0
    })
    recipe_id = r.json()["id"]
    # Log from it
    r2 = client.post("/health/meals/from-recipe", json={"recipe_id": recipe_id})
    assert r2.status_code == 200
    assert "Test Oats" in r2.json()["result"]
    # Verify it showed up in today's meals
    meals = client.get("/health/meals/today").json()["meals"]
    assert any(m["description"] == "Test Oats" for m in meals)

def test_log_from_recipe_not_found(client):
    r = client.post("/health/meals/from-recipe", json={"recipe_id": 99999})
    assert r.status_code == 404
```

- [ ] **Step 5: Run tests**

```bash
cd ~/deep-workspace/chitiyu-pi && python -m pytest tests/test_api_health.py -v -x 2>&1 | tail -30
```

- [ ] **Step 6: Commit**

```bash
cd ~/deep-workspace/chitiyu-pi
git add backend/domains/health/tools.py backend/domains/health/db.py \
        backend/domains/health/router.py tests/test_api_health.py
git commit -m "feat(backend): add meal preview, log-from-recipe endpoints"
```

---

### Task 3: Frontend — api.ts additions

**Files:**
- Modify: `app/lib/api.ts`

**Interfaces:**
- Consumes: backend endpoints from Tasks 1 & 2
- Produces: `deleteMeal(id)`, `getMealPreview(text)`, `logMealFromRecipe(recipeId)`, `getRecipes()`, `createRecipe(...)`, `deleteTransaction(id)`, `getBudgets()`, `setBudget(category, amount)`, updated `logExpense(text, category?)`

- [ ] **Step 1: Add health API functions to api.ts**

Add after the existing `getHealthMetricsToday` line:

```typescript
// ─── Health — additional ───────────────────────────────────────────────────────

export interface MealPreviewResult {
  description: string;
  calories: number;
  protein: number;
  fat: number;
  carbs: number;
}

export interface Recipe {
  id: number;
  name: string;
  calories: number;
  protein: number;
  fat: number | null;
  carbs: number | null;
  serving_unit: string | null;
}

export const deleteMeal = (id: number) =>
  request<{ ok: boolean }>("DELETE", `/health/meals/${id}`);

export const getMealPreview = (text: string) =>
  request<MealPreviewResult>("POST", "/health/meals/preview", { text });

export const logMealFromRecipe = (recipeId: number) =>
  request<{ result: string }>("POST", "/health/meals/from-recipe", { recipe_id: recipeId });

export const getRecipes = () =>
  request<Recipe[]>("GET", "/health/recipes");

export const createRecipe = (name: string, calories: number, protein: number, fat?: number, carbs?: number) =>
  request<{ id: number; name: string }>("POST", "/health/recipes", { name, calories, protein, fat, carbs });
```

- [ ] **Step 2: Add finance API functions to api.ts**

Update the existing `logExpense` and add new functions:

```typescript
// Replace the existing logExpense line:
export const logExpense = (text: string, category?: string) =>
  request<Transaction>("POST", "/finance/transactions", { text, ...(category ? { category } : {}) });

// Add after getSavingsGoals:
export const deleteTransaction = (id: number) =>
  request<{ ok: boolean }>("DELETE", `/finance/transactions/${id}`);

export interface Budget {
  id: number;
  category: string;
  amount: number;
  period: string;
}

export const getBudgets = () =>
  request<Budget[]>("GET", "/finance/budgets");

export const setBudget = (category: string, amount: number) =>
  request<{ id: number; category: string; amount: number }>("POST", "/finance/budgets", { category, amount });
```

- [ ] **Step 3: No automated test for api.ts** (TypeScript types — verified by build + runtime)

- [ ] **Step 4: Commit**

```bash
cd ~/deep-workspace/chitiyu-pi/app
git add lib/api.ts
git commit -m "feat(api): add delete meal/tx, preview, from-recipe, recipes, budgets functions"
```

---

### Task 4: Theme System

**Files:**
- Create: `app/lib/theme.ts`

**Interfaces:**
- Produces: `useTheme()` → `{ colors: Colors, isDark: boolean }`
- Produces: `Colors` type with keys used across all tabs

- [ ] **Step 1: Create app/lib/theme.ts**

```typescript
import { useColorScheme } from "react-native";

export interface Colors {
  background: string;       // page background
  card: string;             // card/sheet background
  cardElevated: string;     // slightly elevated card (modals)
  border: string;           // hairline separator
  borderSubtle: string;     // slightly more visible border
  text: string;             // primary text
  textSecondary: string;    // muted text
  textTertiary: string;     // very muted / placeholder
  accent: string;           // blue primary action
  accentGreen: string;      // success / calorie green
  accentOrange: string;     // warning / calorie orange
  accentPurple: string;     // carbs
  accentRed: string;        // error / overbudget
  tabBar: string;           // tab bar background
  inputBg: string;          // text input background
  checkCircle: string;      // task checkbox border
  overdueStripe: string;    // overdue section left border bg
  swipeDelete: string;      // swipe delete background
}

const dark: Colors = {
  background: "#000000",
  card: "#1C1C1E",
  cardElevated: "#2C2C2E",
  border: "#2C2C2E",
  borderSubtle: "#3A3A3C",
  text: "#FFFFFF",
  textSecondary: "#8E8E93",
  textTertiary: "#636366",
  accent: "#007AFF",
  accentGreen: "#30D158",
  accentOrange: "#FF9F0A",
  accentPurple: "#BF5AF2",
  accentRed: "#FF453A",
  tabBar: "#000000",
  inputBg: "#2C2C2E",
  checkCircle: "#636366",
  overdueStripe: "#1C0A0A",
  swipeDelete: "#FF453A",
};

const light: Colors = {
  background: "#F2F2F7",
  card: "#FFFFFF",
  cardElevated: "#F2F2F7",
  border: "#C6C6C8",
  borderSubtle: "#D1D1D6",
  text: "#000000",
  textSecondary: "#3C3C43CC",
  textTertiary: "#3C3C4399",
  accent: "#007AFF",
  accentGreen: "#34C759",
  accentOrange: "#FF9500",
  accentPurple: "#AF52DE",
  accentRed: "#FF3B30",
  tabBar: "#F9F9F9",
  inputBg: "#FFFFFF",
  checkCircle: "#C7C7CC",
  overdueStripe: "#FFF1F0",
  swipeDelete: "#FF3B30",
};

export function useTheme(): { colors: Colors; isDark: boolean } {
  const scheme = useColorScheme();
  const isDark = scheme === "dark";
  return { colors: isDark ? dark : light, isDark };
}
```

- [ ] **Step 2: Commit**

```bash
cd ~/deep-workspace/chitiyu-pi/app
git add lib/theme.ts
git commit -m "feat(theme): add useTheme hook with dark/light color tokens"
```

---

### Task 5: InsightCard — Expand/Collapse + Dismiss

**Files:**
- Modify: `app/components/InsightCard.tsx`
- Modify: `app/app/(tabs)/index.tsx`

**Interfaces:**
- Consumes: `InsightCard` type from `api.ts` `{title, fact, why, action}`
- `InsightCard` component props: `insight: InsightCardData, index: number, onDismiss: (index: number) => void`

- [ ] **Step 1: Rewrite InsightCard.tsx**

Replace the entire file with:

```typescript
import React, { useState } from "react";
import { View, Text, TouchableOpacity, StyleSheet, LayoutAnimation, Platform, UIManager } from "react-native";
import type { InsightCard as InsightCardData } from "../lib/api";
import { useTheme } from "../lib/theme";

if (Platform.OS === "android" && UIManager.setLayoutAnimationEnabledExperimental) {
  UIManager.setLayoutAnimationEnabledExperimental(true);
}

interface Props {
  insight: InsightCardData;
  index: number;
  onDismiss: (index: number) => void;
}

const ACCENT_COLORS = ["#007AFF", "#30D158", "#FF9F0A", "#BF5AF2", "#32ADE6"];

export function InsightCard({ insight, index, onDismiss }: Props) {
  const [expanded, setExpanded] = useState(false);
  const { colors } = useTheme();
  const accentColor = ACCENT_COLORS[index % ACCENT_COLORS.length];

  const toggle = () => {
    LayoutAnimation.configureNext(LayoutAnimation.Presets.easeInEaseOut);
    setExpanded((e) => !e);
  };

  return (
    <View style={[styles.card, { backgroundColor: colors.card, borderLeftColor: accentColor }]}>
      {/* Header row — always visible */}
      <TouchableOpacity style={styles.headerRow} onPress={toggle} activeOpacity={0.7}>
        <Text style={[styles.title, { color: colors.text }]} numberOfLines={expanded ? undefined : 1}>
          {insight.title}
        </Text>
        <View style={styles.headerActions}>
          <Text style={[styles.chevron, { color: colors.textSecondary }]}>
            {expanded ? "▲" : "▼"}
          </Text>
          <TouchableOpacity
            hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}
            onPress={() => onDismiss(index)}
            style={styles.dismissBtn}
          >
            <Text style={[styles.dismissX, { color: colors.textTertiary }]}>✕</Text>
          </TouchableOpacity>
        </View>
      </TouchableOpacity>

      {/* Expanded body */}
      {expanded && (
        <View style={styles.body}>
          <Text style={[styles.fact, { color: colors.text }]}>{insight.fact}</Text>
          <Text style={[styles.why, { color: colors.textSecondary }]}>{insight.why}</Text>
          <View style={styles.actionRow}>
            <Text style={[styles.arrow, { color: accentColor }]}>→</Text>
            <Text style={[styles.action, { color: accentColor }]}>{insight.action}</Text>
          </View>
        </View>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    borderRadius: 12,
    marginBottom: 10,
    borderLeftWidth: 3,
    overflow: "hidden",
  },
  headerRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    padding: 14,
    gap: 8,
  },
  title: {
    fontSize: 14,
    fontWeight: "600",
    flex: 1,
  },
  headerActions: {
    flexDirection: "row",
    alignItems: "center",
    gap: 10,
  },
  chevron: { fontSize: 10 },
  dismissBtn: { padding: 2 },
  dismissX: { fontSize: 14, fontWeight: "600" },
  body: {
    paddingHorizontal: 14,
    paddingBottom: 14,
    gap: 6,
  },
  fact: { fontSize: 14, lineHeight: 20 },
  why: { fontSize: 13, lineHeight: 18 },
  actionRow: { flexDirection: "row", alignItems: "flex-start", gap: 6, marginTop: 4 },
  arrow: { fontSize: 14, fontWeight: "700" },
  action: { fontSize: 13, fontWeight: "500", flex: 1 },
});
```

- [ ] **Step 2: Update index.tsx — wire dismiss + theme**

In `app/app/(tabs)/index.tsx`:

1. Add import: `import { useTheme } from "../../lib/theme";`
2. Inside `InsightsScreen`, add: `const { colors } = useTheme();` and `const [dismissed, setDismissed] = useState<Set<number>>(new Set());`
3. Add handler: `const handleDismiss = (i: number) => setDismissed((prev) => new Set([...prev, i]));`
4. Filter insights before rendering: `const visibleInsights = insights.filter((_, i) => !dismissed.has(i));`
5. Update the render loop: `{!loading && !generating && visibleInsights.map((insight, i) => (<InsightCard key={i} insight={insight} index={i} onDismiss={handleDismiss} />))}`
6. Replace all hardcoded colors with `colors.*` tokens using the mapping:
   - `backgroundColor: "#000"` → `backgroundColor: colors.background`
   - `backgroundColor: "#1C1C1E"` → `backgroundColor: colors.card`
   - `backgroundColor: "#2C2C2E"` → `backgroundColor: colors.cardElevated`
   - `color: "#fff"` → `color: colors.text`
   - `color: "#8E8E93"` → `color: colors.textSecondary`
   - `color: "#007AFF"` → `color: colors.accent`
   - `color: "#FF453A"` → `color: colors.accentRed`
   - `backgroundColor: "#007AFF"` (buttons) → `backgroundColor: colors.accent`

Full rewritten index.tsx:

```typescript
import React, { useState, useEffect, useCallback } from "react";
import {
  View, Text, ScrollView, TouchableOpacity, Modal,
  ActivityIndicator, RefreshControl, StyleSheet, SafeAreaView,
} from "react-native";
import { InsightCard } from "../../components/InsightCard";
import { getInsightsLatest, generateInsights, type InsightCard as InsightCardData } from "../../lib/api";
import { useTheme } from "../../lib/theme";

type Scope = "today" | "week";

export default function InsightsScreen() {
  const { colors } = useTheme();
  const [insights, setInsights] = useState<InsightCardData[]>([]);
  const [dismissed, setDismissed] = useState<Set<number>>(new Set());
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [modalVisible, setModalVisible] = useState(false);
  const [modalScope, setModalScope] = useState<Scope>("today");
  const [activeScope, setActiveScope] = useState<Scope>("today");
  const [error, setError] = useState<string | null>(null);

  const loadInsights = useCallback(async () => {
    setError(null);
    try {
      const data = await getInsightsLatest(activeScope);
      setInsights(data.cards);
      setDismissed(new Set()); // reset dismissed on reload
    } catch (e) {
      if (e instanceof Error && e.message.includes("404")) {
        setInsights([]);
      } else {
        setError(e instanceof Error ? e.message : "Failed to load insights");
      }
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [activeScope]);

  useEffect(() => { loadInsights(); }, [loadInsights]);

  const handleDismiss = (i: number) =>
    setDismissed((prev) => new Set([...prev, i]));

  const handleGenerate = async () => {
    setGenerating(true);
    setModalVisible(false);
    setActiveScope(modalScope);
    try {
      await generateInsights(modalScope);
      let data = null;
      for (let attempt = 0; attempt < 10; attempt++) {
        await new Promise((r) => setTimeout(r, 2000));
        try {
          data = await getInsightsLatest(modalScope);
          if (data.cards.length > 0) break;
        } catch { /* 404 = not ready */ }
      }
      if (data) { setInsights(data.cards); setDismissed(new Set()); }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to generate insights");
    } finally {
      setGenerating(false);
    }
  };

  const today = new Date().toLocaleDateString("en-US", { weekday: "long", month: "long", day: "numeric" });
  const visibleInsights = insights.filter((_, i) => !dismissed.has(i));

  const s = makeStyles(colors);

  return (
    <SafeAreaView style={s.safe}>
      <ScrollView
        style={s.scroll}
        contentContainerStyle={s.content}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={loadInsights} />}
      >
        <View style={s.header}>
          <View>
            <Text style={s.appName}>Chitiyu</Text>
            <Text style={s.date}>{today}</Text>
          </View>
          <TouchableOpacity style={s.refreshButton} onPress={() => setModalVisible(true)}>
            <Text style={s.refreshText}>↻ Refresh</Text>
          </TouchableOpacity>
        </View>

        <View style={s.scopeRow}>
          {(["today", "week"] as Scope[]).map((sc) => (
            <TouchableOpacity
              key={sc}
              style={[s.scopeButton, activeScope === sc && s.scopeButtonActive]}
              onPress={() => setActiveScope(sc)}
            >
              <Text style={[s.scopeText, activeScope === sc && s.scopeTextActive]}>
                {sc === "today" ? "Today" : "This Week"}
              </Text>
            </TouchableOpacity>
          ))}
        </View>

        {loading && (
          <View style={s.centerState}>
            <ActivityIndicator color={colors.accent} />
            <Text style={s.stateText}>Loading insights…</Text>
          </View>
        )}
        {generating && (
          <View style={s.centerState}>
            <ActivityIndicator color={colors.accent} />
            <Text style={s.stateText}>Generating insights…</Text>
          </View>
        )}
        {error && !loading && (
          <View style={s.centerState}>
            <Text style={s.errorText}>{error}</Text>
          </View>
        )}
        {!loading && !generating && !error && insights.length === 0 && (
          <View style={s.centerState}>
            <Text style={s.emptyText}>No insights yet.</Text>
            <Text style={s.emptySubtext}>Log a meal or expense to get started.</Text>
          </View>
        )}
        {!loading && !generating && !error && insights.length > 0 && visibleInsights.length === 0 && (
          <View style={s.centerState}>
            <Text style={s.emptyText}>All caught up.</Text>
            <Text style={s.emptySubtext}>Pull down to refresh or generate new insights.</Text>
          </View>
        )}
        {!loading && !generating && visibleInsights.map((insight, i) => (
          <InsightCard key={i} insight={insight} index={i} onDismiss={handleDismiss} />
        ))}
      </ScrollView>

      <Modal visible={modalVisible} transparent animationType="slide" onRequestClose={() => setModalVisible(false)}>
        <View style={s.modalOverlay}>
          <View style={s.modalSheet}>
            <Text style={s.modalTitle}>Generate Insights</Text>
            <View style={s.scopeRow}>
              {(["today", "week"] as Scope[]).map((sc) => (
                <TouchableOpacity
                  key={sc}
                  style={[s.scopeButton, modalScope === sc && s.scopeButtonActive]}
                  onPress={() => setModalScope(sc)}
                >
                  <Text style={[s.scopeText, modalScope === sc && s.scopeTextActive]}>
                    {sc === "today" ? "Today" : "This Week"}
                  </Text>
                </TouchableOpacity>
              ))}
            </View>
            <TouchableOpacity style={s.generateButton} onPress={handleGenerate}>
              <Text style={s.generateText}>Generate</Text>
            </TouchableOpacity>
            <TouchableOpacity style={s.cancelButton} onPress={() => setModalVisible(false)}>
              <Text style={s.cancelText}>Cancel</Text>
            </TouchableOpacity>
          </View>
        </View>
      </Modal>
    </SafeAreaView>
  );
}

function makeStyles(colors: ReturnType<typeof import("../../lib/theme").useTheme>["colors"]) {
  return StyleSheet.create({
    safe: { flex: 1, backgroundColor: colors.background },
    scroll: { flex: 1 },
    content: { padding: 16, paddingBottom: 32 },
    header: { flexDirection: "row", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 20 },
    appName: { color: colors.text, fontSize: 26, fontWeight: "700", letterSpacing: -0.5 },
    date: { color: colors.textSecondary, fontSize: 13, marginTop: 2 },
    refreshButton: { backgroundColor: colors.card, paddingHorizontal: 12, paddingVertical: 7, borderRadius: 8, marginTop: 4 },
    refreshText: { color: colors.accent, fontSize: 14, fontWeight: "500" },
    centerState: { alignItems: "center", paddingVertical: 60, gap: 8 },
    stateText: { color: colors.textSecondary, fontSize: 14, marginTop: 8 },
    errorText: { color: colors.accentRed, fontSize: 14, textAlign: "center" },
    emptyText: { color: colors.text, fontSize: 16, fontWeight: "600" },
    emptySubtext: { color: colors.textSecondary, fontSize: 14, textAlign: "center" },
    modalOverlay: { flex: 1, backgroundColor: "#00000088", justifyContent: "flex-end" },
    modalSheet: { backgroundColor: colors.card, borderTopLeftRadius: 20, borderTopRightRadius: 20, padding: 24, paddingBottom: 40 },
    modalTitle: { color: colors.text, fontSize: 17, fontWeight: "600", textAlign: "center", marginBottom: 20 },
    scopeRow: { flexDirection: "row", gap: 12, marginBottom: 20 },
    scopeButton: { flex: 1, backgroundColor: colors.cardElevated, borderRadius: 10, paddingVertical: 12, alignItems: "center" },
    scopeButtonActive: { backgroundColor: colors.accent },
    scopeText: { color: colors.textSecondary, fontWeight: "500" },
    scopeTextActive: { color: "#fff" },
    generateButton: { backgroundColor: colors.accent, borderRadius: 12, paddingVertical: 14, alignItems: "center", marginBottom: 10 },
    generateText: { color: "#fff", fontSize: 16, fontWeight: "600" },
    cancelButton: { alignItems: "center", paddingVertical: 10 },
    cancelText: { color: colors.textSecondary, fontSize: 15 },
  });
}
```

- [ ] **Step 3: Commit**

```bash
cd ~/deep-workspace/chitiyu-pi/app
git add components/InsightCard.tsx app/\(tabs\)/index.tsx
git commit -m "feat(insights): collapse/expand cards, dismiss, theme colors"
```

---

### Task 6: Health Tab — Meal Sections, Swipe Delete, Confirmation, Recipe Quick-Select

**Files:**
- Create: `app/components/MealRow.tsx`
- Modify: `app/app/(tabs)/health.tsx`

**Interfaces:**
- Consumes: `deleteMeal`, `getMealPreview`, `logMealFromRecipe`, `getRecipes`, `createRecipe`, `MealPreviewResult`, `Recipe` from `api.ts`
- Consumes: `useTheme` from `lib/theme.ts`
- `MealRow` props: `meal: Meal, onDelete: (id: number) => void, colors: Colors`

- [ ] **Step 1: Create MealRow.tsx**

```typescript
import React, { useRef } from "react";
import { View, Text, TouchableOpacity, Animated, PanResponder, StyleSheet } from "react-native";
import type { Meal } from "../lib/api";
import type { Colors } from "../lib/theme";

interface Props {
  meal: Meal;
  onDelete: (id: number) => void;
  colors: Colors;
}

const SWIPE_THRESHOLD = -80;

export function MealRow({ meal, onDelete, colors }: Props) {
  const translateX = useRef(new Animated.Value(0)).current;
  const deleteOpacity = translateX.interpolate({
    inputRange: [SWIPE_THRESHOLD, 0],
    outputRange: [1, 0],
    extrapolate: "clamp",
  });

  const panResponder = PanResponder.create({
    onMoveShouldSetPanResponder: (_, { dx }) => Math.abs(dx) > 10,
    onPanResponderMove: (_, { dx }) => { if (dx < 0) translateX.setValue(dx); },
    onPanResponderRelease: (_, { dx }) => {
      if (dx < SWIPE_THRESHOLD) {
        Animated.timing(translateX, { toValue: -120, duration: 150, useNativeDriver: true }).start(
          () => onDelete(meal.id)
        );
      } else {
        Animated.spring(translateX, { toValue: 0, useNativeDriver: true }).start();
      }
    },
  });

  const formatTime = (iso: string) =>
    new Date(iso).toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit" });

  return (
    <View style={styles.container}>
      <Animated.View style={[styles.deleteBackground, { opacity: deleteOpacity, backgroundColor: colors.swipeDelete }]}>
        <Text style={styles.deleteLabel}>Delete</Text>
      </Animated.View>
      <Animated.View
        style={[styles.row, { transform: [{ translateX }], backgroundColor: colors.background, borderBottomColor: colors.border }]}
        {...panResponder.panHandlers}
      >
        <View style={styles.info}>
          <Text style={[styles.desc, { color: colors.text }]}>{meal.description}</Text>
          <Text style={[styles.time, { color: colors.textSecondary }]}>{formatTime(meal.logged_at)}</Text>
        </View>
        <Text style={[styles.kcal, { color: colors.accentOrange }]}>{meal.calories} kcal</Text>
      </Animated.View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { position: "relative", overflow: "hidden" },
  deleteBackground: {
    position: "absolute", right: 0, top: 0, bottom: 0, width: 120,
    alignItems: "center", justifyContent: "center",
  },
  deleteLabel: { color: "#fff", fontWeight: "600", fontSize: 14 },
  row: {
    flexDirection: "row", justifyContent: "space-between", alignItems: "center",
    paddingVertical: 10, paddingHorizontal: 4,
    borderBottomWidth: StyleSheet.hairlineWidth,
  },
  info: { flex: 1, marginRight: 12 },
  desc: { fontSize: 14 },
  time: { fontSize: 12, marginTop: 2 },
  kcal: { fontSize: 14, fontWeight: "600" },
});
```

- [ ] **Step 2: Rewrite health.tsx**

Full replacement of `app/app/(tabs)/health.tsx`:

```typescript
import React, { useState, useEffect, useCallback } from "react";
import {
  View, Text, ScrollView, TouchableOpacity, Modal, TextInput,
  ActivityIndicator, RefreshControl, StyleSheet, SafeAreaView,
  KeyboardAvoidingView, Platform, FlatList,
} from "react-native";
import { ProgressBar } from "../../components/ProgressBar";
import { MacroRings } from "../../components/MacroRings";
import { MealRow } from "../../components/MealRow";
import {
  getMealsToday, logMeal, getHealthMetricsToday, getMealPreview,
  logMealFromRecipe, getRecipes, createRecipe, deleteMeal,
  type Meal, type MealTotals, type HealthMetrics, type MealPreviewResult, type Recipe,
} from "../../lib/api";
import { TARGETS } from "../../constants/targets";
import { useTheme } from "../../lib/theme";

type MealSection = { label: string; meals: Meal[] };
type LogTab = "describe" | "recipes";

function bucketMeals(meals: Meal[]): MealSection[] {
  const sections: { label: string; hours: [number, number] }[] = [
    { label: "Breakfast", hours: [0, 11] },
    { label: "Lunch", hours: [11, 15] },
    { label: "Dinner", hours: [15, 20] },
    { label: "Late Night", hours: [20, 24] },
  ];
  return sections
    .map(({ label, hours: [start, end] }) => ({
      label,
      meals: meals.filter((m) => {
        const hour = new Date(m.logged_at).getHours();
        return hour >= start && hour < end;
      }),
    }))
    .filter((s) => s.meals.length > 0);
}

export default function HealthScreen() {
  const { colors } = useTheme();
  const [meals, setMeals] = useState<Meal[]>([]);
  const [totals, setTotals] = useState<MealTotals>({ calories: 0, protein: 0, fat: 0, carbs: 0 });
  const [metrics, setMetrics] = useState<HealthMetrics | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Sheet state
  const [sheetVisible, setSheetVisible] = useState(false);
  const [logTab, setLogTab] = useState<LogTab>("describe");
  const [mealInput, setMealInput] = useState("");

  // Preview/confirm flow
  const [previewing, setPreviewing] = useState(false);
  const [preview, setPreview] = useState<MealPreviewResult | null>(null);
  const [logging, setLogging] = useState(false);

  // Recipe state
  const [recipes, setRecipes] = useState<Recipe[]>([]);
  const [recipesLoading, setRecipesLoading] = useState(false);
  const [savingRecipe, setSavingRecipe] = useState(false);
  const [showSaveRecipe, setShowSaveRecipe] = useState(false);
  const [recipeName, setRecipeName] = useState("");

  const loadData = useCallback(async () => {
    setError(null);
    try {
      const [mealsData, metricsData] = await Promise.all([
        getMealsToday(),
        getHealthMetricsToday(),
      ]);
      setMeals(mealsData.meals);
      setTotals(mealsData.totals);
      setMetrics(metricsData);
    } catch (e: any) {
      setError(e?.message ?? "Failed to load health data");
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  const loadRecipes = useCallback(async () => {
    setRecipesLoading(true);
    try {
      const data = await getRecipes();
      setRecipes(data);
    } finally {
      setRecipesLoading(false);
    }
  }, []);

  useEffect(() => { loadData(); }, [loadData]);

  const handleRefresh = () => { setRefreshing(true); loadData(); };

  const openSheet = () => {
    setPreview(null);
    setMealInput("");
    setLogTab("describe");
    setShowSaveRecipe(false);
    setSheetVisible(true);
  };

  const handleSwitchToRecipes = () => {
    setLogTab("recipes");
    if (recipes.length === 0) loadRecipes();
  };

  const handlePreview = async () => {
    if (!mealInput.trim()) return;
    setPreviewing(true);
    try {
      const result = await getMealPreview(mealInput.trim());
      setPreview(result);
      setRecipeName(result.description);
    } finally {
      setPreviewing(false);
    }
  };

  const handleConfirmLog = async () => {
    if (!preview) return;
    setLogging(true);
    try {
      await logMeal(mealInput.trim());
      setSheetVisible(false);
      setPreview(null);
      setMealInput("");
      await loadData();
      // Ask to save as recipe
      setShowSaveRecipe(true);
    } finally {
      setLogging(false);
    }
  };

  const handleSaveAsRecipe = async () => {
    if (!preview || !recipeName.trim()) return;
    setSavingRecipe(true);
    try {
      await createRecipe(
        recipeName.trim(), preview.calories, preview.protein,
        preview.fat ?? undefined, preview.carbs ?? undefined
      );
      await loadRecipes();
    } finally {
      setSavingRecipe(false);
      setShowSaveRecipe(false);
    }
  };

  const handleLogFromRecipe = async (recipeId: number) => {
    setLogging(true);
    try {
      await logMealFromRecipe(recipeId);
      setSheetVisible(false);
      await loadData();
    } finally {
      setLogging(false);
    }
  };

  const handleDeleteMeal = async (id: number) => {
    await deleteMeal(id);
    setMeals((prev) => prev.filter((m) => m.id !== id));
    // Reload totals
    const mealsData = await getMealsToday();
    setTotals(mealsData.totals);
  };

  const mealSections = bucketMeals(meals);

  if (loading) {
    return (
      <SafeAreaView style={{ flex: 1, backgroundColor: colors.background }}>
        <View style={styles.center}><ActivityIndicator color={colors.accent} /></View>
      </SafeAreaView>
    );
  }

  if (error) {
    return (
      <SafeAreaView style={{ flex: 1, backgroundColor: colors.background }}>
        <View style={styles.center}>
          <Text style={{ color: colors.accentRed, fontSize: 15, textAlign: "center", padding: 20 }}>{error}</Text>
        </View>
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: colors.background }}>
      <ScrollView
        style={{ flex: 1 }}
        contentContainerStyle={styles.content}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={handleRefresh} />}
      >
        {/* Macro progress */}
        <View style={styles.section}>
          <ProgressBar label="Calories" value={totals.calories} target={TARGETS.calories} unit=" kcal" color={colors.accentOrange} />
          <ProgressBar label="Protein" value={totals.protein} target={TARGETS.protein} unit="g" color={colors.accentGreen} />
          <ProgressBar label="Fat" value={totals.fat} target={TARGETS.fat} unit="g" color={colors.accentOrange} />
          <ProgressBar label="Carbs" value={totals.carbs} target={TARGETS.carbs} unit="g" color={colors.accentPurple} />
        </View>

        <MacroRings totals={totals} />

        {metrics?.steps != null && (
          <View style={styles.section}>
            <ProgressBar label="Steps" value={metrics.steps} target={TARGETS.steps} unit="" color={colors.accent} />
          </View>
        )}

        {metrics && (metrics.sleep_total_mins != null || metrics.sleep_deep_mins != null || metrics.resting_hr != null) && (
          <View style={[styles.card, { backgroundColor: colors.card }]}>
            <Text style={[styles.sectionTitle, { color: colors.text }]}>Last Night</Text>
            <View style={styles.metricsRow}>
              <MetricChip label="Deep sleep" value={metrics.sleep_deep_mins != null ? `${metrics.sleep_deep_mins}m` : "—"} target={`/ ${TARGETS.deepSleepMins}m`} ok={metrics.sleep_deep_mins != null ? metrics.sleep_deep_mins >= TARGETS.deepSleepMins : undefined} colors={colors} />
              <MetricChip label="Total sleep" value={metrics.sleep_total_mins != null ? `${Math.round(metrics.sleep_total_mins / 60)}h ${metrics.sleep_total_mins % 60}m` : "—"} colors={colors} />
              <MetricChip label="Resting HR" value={metrics.resting_hr != null ? `${metrics.resting_hr} bpm` : "—"} colors={colors} />
            </View>
          </View>
        )}

        {/* Log Meal CTA */}
        <TouchableOpacity style={[styles.primaryButton, { backgroundColor: colors.accent }]} onPress={openSheet}>
          <Text style={styles.primaryButtonText}>+ Log Meal</Text>
        </TouchableOpacity>

        {/* Today's meals by section */}
        {meals.length === 0 ? (
          <Text style={[styles.emptyText, { color: colors.textSecondary }]}>No meals logged yet.</Text>
        ) : (
          mealSections.map((section) => (
            <View key={section.label} style={styles.section}>
              <Text style={[styles.sectionTitle, { color: colors.text }]}>{section.label}</Text>
              <View style={[styles.mealGroup, { borderColor: colors.border }]}>
                {section.meals.map((meal) => (
                  <MealRow key={meal.id} meal={meal} onDelete={handleDeleteMeal} colors={colors} />
                ))}
              </View>
            </View>
          ))
        )}
      </ScrollView>

      {/* Log Meal Sheet */}
      <Modal visible={sheetVisible} transparent animationType="slide" onRequestClose={() => setSheetVisible(false)}>
        <KeyboardAvoidingView behavior={Platform.OS === "ios" ? "padding" : undefined} style={styles.modalOverlay}>
          <View style={[styles.modalSheet, { backgroundColor: colors.card }]}>
            <Text style={[styles.modalTitle, { color: colors.text }]}>Log a Meal</Text>

            {/* Tab switcher */}
            <View style={[styles.tabRow, { backgroundColor: colors.cardElevated }]}>
              <TouchableOpacity
                style={[styles.tabBtn, logTab === "describe" && { backgroundColor: colors.card }]}
                onPress={() => setLogTab("describe")}
              >
                <Text style={[styles.tabText, { color: logTab === "describe" ? colors.text : colors.textSecondary }]}>Describe</Text>
              </TouchableOpacity>
              <TouchableOpacity
                style={[styles.tabBtn, logTab === "recipes" && { backgroundColor: colors.card }]}
                onPress={handleSwitchToRecipes}
              >
                <Text style={[styles.tabText, { color: logTab === "recipes" ? colors.text : colors.textSecondary }]}>Quick Select</Text>
              </TouchableOpacity>
            </View>

            {logTab === "describe" ? (
              <>
                {preview ? (
                  // Confirmation view
                  <View style={styles.previewBox}>
                    <Text style={[styles.previewName, { color: colors.text }]}>{preview.description}</Text>
                    <View style={styles.macroChips}>
                      <MacroChip label="Cal" value={`${preview.calories}`} color={colors.accentOrange} />
                      <MacroChip label="Pro" value={`${preview.protein}g`} color={colors.accentGreen} />
                      {preview.fat != null && <MacroChip label="Fat" value={`${preview.fat}g`} color={colors.accentOrange} />}
                      {preview.carbs != null && <MacroChip label="Carbs" value={`${preview.carbs}g`} color={colors.accentPurple} />}
                    </View>
                    <Text style={[styles.previewQuestion, { color: colors.textSecondary }]}>Does this look right?</Text>
                    <View style={styles.confirmRow}>
                      <TouchableOpacity
                        style={[styles.confirmBtn, { backgroundColor: colors.accentGreen }]}
                        onPress={handleConfirmLog}
                        disabled={logging}
                      >
                        {logging ? <ActivityIndicator color="#fff" /> : <Text style={styles.confirmBtnText}>Log it</Text>}
                      </TouchableOpacity>
                      <TouchableOpacity
                        style={[styles.confirmBtn, { backgroundColor: colors.cardElevated }]}
                        onPress={() => setPreview(null)}
                      >
                        <Text style={[styles.confirmBtnText, { color: colors.text }]}>Edit</Text>
                      </TouchableOpacity>
                    </View>
                  </View>
                ) : (
                  // Input view
                  <>
                    <TextInput
                      style={[styles.textInput, { backgroundColor: colors.inputBg, color: colors.text }]}
                      value={mealInput}
                      onChangeText={setMealInput}
                      placeholder="e.g. 2 eggs, turkey bacon, sourdough toast"
                      placeholderTextColor={colors.textTertiary}
                      multiline
                      autoFocus
                    />
                    <TouchableOpacity
                      style={[styles.generateButton, { backgroundColor: colors.accent }, (previewing || !mealInput.trim()) && styles.buttonDisabled]}
                      onPress={handlePreview}
                      disabled={previewing || !mealInput.trim()}
                    >
                      {previewing ? <ActivityIndicator color="#fff" /> : <Text style={styles.generateText}>Analyze</Text>}
                    </TouchableOpacity>
                  </>
                )}
              </>
            ) : (
              // Recipes tab
              <>
                {recipesLoading ? (
                  <ActivityIndicator color={colors.accent} style={{ marginVertical: 30 }} />
                ) : recipes.length === 0 ? (
                  <View style={styles.emptyState}>
                    <Text style={[styles.emptyStateText, { color: colors.textSecondary }]}>No saved recipes yet.</Text>
                    <Text style={[styles.emptyStateSubtext, { color: colors.textTertiary }]}>Log a meal and save it as a recipe for quick access.</Text>
                  </View>
                ) : (
                  <FlatList
                    data={recipes}
                    keyExtractor={(r) => String(r.id)}
                    style={{ maxHeight: 300 }}
                    renderItem={({ item }) => (
                      <TouchableOpacity
                        style={[styles.recipeRow, { borderBottomColor: colors.border }]}
                        onPress={() => handleLogFromRecipe(item.id)}
                        disabled={logging}
                      >
                        <Text style={[styles.recipeName, { color: colors.text }]}>{item.name}</Text>
                        <Text style={[styles.recipeKcal, { color: colors.accentOrange }]}>{item.calories} kcal</Text>
                      </TouchableOpacity>
                    )}
                  />
                )}
              </>
            )}

            <TouchableOpacity style={styles.cancelButton} onPress={() => setSheetVisible(false)}>
              <Text style={[styles.cancelText, { color: colors.textSecondary }]}>Cancel</Text>
            </TouchableOpacity>
          </View>
        </KeyboardAvoidingView>
      </Modal>

      {/* Save as Recipe prompt */}
      <Modal visible={showSaveRecipe} transparent animationType="fade" onRequestClose={() => setShowSaveRecipe(false)}>
        <View style={styles.modalOverlay}>
          <View style={[styles.modalSheet, { backgroundColor: colors.card }]}>
            <Text style={[styles.modalTitle, { color: colors.text }]}>Save as Recipe?</Text>
            <TextInput
              style={[styles.textInput, { backgroundColor: colors.inputBg, color: colors.text, minHeight: 0 }]}
              value={recipeName}
              onChangeText={setRecipeName}
              placeholder="Recipe name"
              placeholderTextColor={colors.textTertiary}
              autoFocus
            />
            <View style={styles.confirmRow}>
              <TouchableOpacity
                style={[styles.confirmBtn, { backgroundColor: colors.accent }]}
                onPress={handleSaveAsRecipe}
                disabled={savingRecipe}
              >
                {savingRecipe ? <ActivityIndicator color="#fff" /> : <Text style={styles.confirmBtnText}>Save</Text>}
              </TouchableOpacity>
              <TouchableOpacity
                style={[styles.confirmBtn, { backgroundColor: colors.cardElevated }]}
                onPress={() => setShowSaveRecipe(false)}
              >
                <Text style={[styles.confirmBtnText, { color: colors.text }]}>Skip</Text>
              </TouchableOpacity>
            </View>
          </View>
        </View>
      </Modal>
    </SafeAreaView>
  );
}

function MetricChip({ label, value, target, ok, colors }: {
  label: string; value: string; target?: string; ok?: boolean; colors: any;
}) {
  return (
    <View style={chipStyles.chip}>
      <Text style={[chipStyles.label, { color: colors.textSecondary }]}>{label}</Text>
      <Text style={[chipStyles.value, { color: ok === false ? colors.accentRed : colors.text }]}>{value}</Text>
      {target && <Text style={[chipStyles.target, { color: colors.textSecondary }]}>{target}</Text>}
    </View>
  );
}

function MacroChip({ label, value, color }: { label: string; value: string; color: string }) {
  return (
    <View style={[chipStyles.macroChip, { backgroundColor: color + "22" }]}>
      <Text style={[chipStyles.macroLabel, { color }]}>{label}</Text>
      <Text style={[chipStyles.macroValue, { color }]}>{value}</Text>
    </View>
  );
}

const chipStyles = StyleSheet.create({
  chip: { alignItems: "center", flex: 1 },
  label: { fontSize: 11, marginBottom: 3 },
  value: { fontSize: 15, fontWeight: "600" },
  target: { fontSize: 11, marginTop: 1 },
  macroChip: { borderRadius: 8, paddingHorizontal: 10, paddingVertical: 6, alignItems: "center" },
  macroLabel: { fontSize: 10, fontWeight: "600", textTransform: "uppercase" },
  macroValue: { fontSize: 14, fontWeight: "700" },
});

const styles = StyleSheet.create({
  center: { flex: 1, alignItems: "center", justifyContent: "center" },
  content: { padding: 16, paddingBottom: 40 },
  section: { marginBottom: 20 },
  card: { borderRadius: 12, padding: 16, marginBottom: 20 },
  sectionTitle: { fontSize: 15, fontWeight: "600", marginBottom: 8 },
  metricsRow: { flexDirection: "row", justifyContent: "space-around" },
  primaryButton: { borderRadius: 12, paddingVertical: 14, alignItems: "center", marginBottom: 24 },
  primaryButtonText: { color: "#fff", fontSize: 16, fontWeight: "600" },
  mealGroup: { borderRadius: 10, borderWidth: StyleSheet.hairlineWidth, overflow: "hidden" },
  emptyText: { fontSize: 14 },
  // Modal
  modalOverlay: { flex: 1, backgroundColor: "#00000088", justifyContent: "flex-end" },
  modalSheet: { borderTopLeftRadius: 20, borderTopRightRadius: 20, padding: 24, paddingBottom: 40 },
  modalTitle: { fontSize: 17, fontWeight: "600", marginBottom: 16 },
  tabRow: { flexDirection: "row", borderRadius: 10, padding: 3, marginBottom: 16 },
  tabBtn: { flex: 1, paddingVertical: 8, alignItems: "center", borderRadius: 8 },
  tabText: { fontSize: 14, fontWeight: "500" },
  textInput: { borderRadius: 10, padding: 14, fontSize: 15, minHeight: 80, textAlignVertical: "top", marginBottom: 16 },
  generateButton: { borderRadius: 12, paddingVertical: 14, alignItems: "center", marginBottom: 10 },
  buttonDisabled: { opacity: 0.5 },
  generateText: { color: "#fff", fontSize: 16, fontWeight: "600" },
  cancelButton: { alignItems: "center", paddingVertical: 10 },
  cancelText: { fontSize: 15 },
  // Preview
  previewBox: { marginBottom: 16 },
  previewName: { fontSize: 16, fontWeight: "600", marginBottom: 10 },
  macroChips: { flexDirection: "row", gap: 8, flexWrap: "wrap", marginBottom: 12 },
  previewQuestion: { fontSize: 14, marginBottom: 12 },
  confirmRow: { flexDirection: "row", gap: 10 },
  confirmBtn: { flex: 1, borderRadius: 10, paddingVertical: 12, alignItems: "center" },
  confirmBtnText: { color: "#fff", fontSize: 15, fontWeight: "600" },
  // Recipes
  recipeRow: { flexDirection: "row", justifyContent: "space-between", alignItems: "center", paddingVertical: 12, borderBottomWidth: StyleSheet.hairlineWidth },
  recipeName: { fontSize: 15, fontWeight: "500", flex: 1 },
  recipeKcal: { fontSize: 13, fontWeight: "600" },
  emptyState: { paddingVertical: 30, alignItems: "center", gap: 6 },
  emptyStateText: { fontSize: 15, fontWeight: "600" },
  emptyStateSubtext: { fontSize: 13, textAlign: "center" },
});
```

- [ ] **Step 3: Commit**

```bash
cd ~/deep-workspace/chitiyu-pi/app
git add components/MealRow.tsx app/\(tabs\)/health.tsx
git commit -m "feat(health): meal sections, calorie confirm, recipe quick-select, swipe delete"
```

---

### Task 7: Finance Tab — Delete, Budget Edit, Category Picker

**Files:**
- Modify: `app/components/TransactionRow.tsx`
- Modify: `app/app/(tabs)/finance.tsx`

**Interfaces:**
- Consumes: `deleteTransaction`, `getBudgets`, `setBudget`, `Budget`, `logExpense` (with category) from `api.ts`
- Consumes: `useTheme` from `lib/theme.ts`
- `TransactionRow` new props: `onDelete?: (id: number) => void`

- [ ] **Step 1: Rewrite TransactionRow.tsx with swipe-to-delete**

```typescript
import React, { useRef } from "react";
import { View, Text, TouchableOpacity, Animated, PanResponder, StyleSheet } from "react-native";
import type { Transaction } from "../lib/api";
import { useTheme } from "../lib/theme";

interface Props {
  transaction: Transaction;
  onDelete?: (id: number) => void;
}

const SWIPE_THRESHOLD = -80;

export function TransactionRow({ transaction, onDelete }: Props) {
  const { colors } = useTheme();
  const translateX = useRef(new Animated.Value(0)).current;
  const deleteOpacity = translateX.interpolate({
    inputRange: [SWIPE_THRESHOLD, 0],
    outputRange: [1, 0],
    extrapolate: "clamp",
  });

  const panResponder = PanResponder.create({
    onMoveShouldSetPanResponder: (_, { dx }) => onDelete != null && Math.abs(dx) > 10,
    onPanResponderMove: (_, { dx }) => { if (dx < 0) translateX.setValue(dx); },
    onPanResponderRelease: (_, { dx }) => {
      if (dx < SWIPE_THRESHOLD && onDelete) {
        Animated.timing(translateX, { toValue: -120, duration: 150, useNativeDriver: true }).start(
          () => onDelete(transaction.id)
        );
      } else {
        Animated.spring(translateX, { toValue: 0, useNativeDriver: true }).start();
      }
    },
  });

  const isCredit = transaction.amount > 0;
  const formatted = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(Math.abs(transaction.amount));
  const date = new Date(transaction.date).toLocaleDateString("en-US", { month: "short", day: "numeric" });

  return (
    <View style={styles.container}>
      {onDelete && (
        <Animated.View style={[styles.deleteBackground, { opacity: deleteOpacity, backgroundColor: colors.swipeDelete }]}>
          <Text style={styles.deleteLabel}>Delete</Text>
        </Animated.View>
      )}
      <Animated.View
        style={[styles.row, { transform: [{ translateX }], backgroundColor: colors.background, borderBottomColor: colors.border }]}
        {...(onDelete ? panResponder.panHandlers : {})}
      >
        <View style={styles.info}>
          <Text style={[styles.desc, { color: colors.text }]}>{transaction.description}</Text>
          <Text style={[styles.meta, { color: colors.textSecondary }]}>{transaction.category} · {date}</Text>
        </View>
        <Text style={[styles.amount, { color: isCredit ? colors.accentGreen : colors.text }]}>
          {isCredit ? "+" : "-"}{formatted}
        </Text>
      </Animated.View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { position: "relative", overflow: "hidden" },
  deleteBackground: {
    position: "absolute", right: 0, top: 0, bottom: 0, width: 120,
    alignItems: "center", justifyContent: "center",
  },
  deleteLabel: { color: "#fff", fontWeight: "600", fontSize: 14 },
  row: {
    flexDirection: "row", justifyContent: "space-between", alignItems: "center",
    paddingVertical: 12, borderBottomWidth: StyleSheet.hairlineWidth,
  },
  info: { flex: 1, marginRight: 12 },
  desc: { fontSize: 14 },
  meta: { fontSize: 12, marginTop: 2 },
  amount: { fontSize: 14, fontWeight: "600" },
});
```

- [ ] **Step 2: Rewrite finance.tsx**

Full replacement of `app/app/(tabs)/finance.tsx`:

```typescript
import React, { useState, useEffect, useCallback } from "react";
import {
  View, Text, ScrollView, TouchableOpacity, Modal, TextInput,
  ActivityIndicator, RefreshControl, StyleSheet, SafeAreaView,
  KeyboardAvoidingView, Platform, Alert,
} from "react-native";
import { ProgressBar } from "../../components/ProgressBar";
import { TransactionRow } from "../../components/TransactionRow";
import {
  getFinanceSummary, getTransactions, logExpense, getNetWorth, getSavingsGoals,
  deleteTransaction, getBudgets, setBudget,
  type CategoryBudget, type Transaction, type NetWorth, type SavingsGoal, type Budget,
} from "../../lib/api";
import { useTheme } from "../../lib/theme";

const EXPENSE_CATEGORIES = ["Food", "Groceries", "Transport", "Entertainment", "Health", "Shopping", "Bills", "Other"];

export default function FinanceScreen() {
  const { colors } = useTheme();
  const now = new Date();
  const [summary, setSummary] = useState<{ total_spent: number; total_budget: number | null; categories: CategoryBudget[] } | null>(null);
  const [transactions, setTransactions] = useState<Transaction[]>([]);
  const [netWorth, setNetWorth] = useState<NetWorth | null>(null);
  const [goals, setGoals] = useState<SavingsGoal[]>([]);
  const [budgets, setBudgets] = useState<Budget[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Log expense sheet
  const [sheetVisible, setSheetVisible] = useState(false);
  const [expenseInput, setExpenseInput] = useState("");
  const [selectedCategory, setSelectedCategory] = useState<string | null>(null);
  const [logging, setLogging] = useState(false);

  // Budget edit modal
  const [budgetModalVisible, setBudgetModalVisible] = useState(false);
  const [editingCategory, setEditingCategory] = useState<string | null>(null);
  const [budgetInput, setBudgetInput] = useState("");
  const [savingBudget, setSavingBudget] = useState(false);

  const loadData = useCallback(async () => {
    setError(null);
    try {
      const [sumData, txData, nwData, goalsData, budgetsData] = await Promise.all([
        getFinanceSummary(now.getFullYear(), now.getMonth() + 1),
        getTransactions(),
        getNetWorth(),
        getSavingsGoals(),
        getBudgets(),
      ]);
      setSummary(sumData);
      setTransactions(txData.transactions.slice(0, 20));
      setNetWorth(nwData);
      setGoals(goalsData.goals);
      setBudgets(budgetsData);
    } catch (e: any) {
      setError(e?.message ?? "Failed to load finance data");
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => { loadData(); }, [loadData]);

  const handleRefresh = () => { setRefreshing(true); loadData(); };

  const handleLogExpense = async () => {
    if (!expenseInput.trim()) return;
    setLogging(true);
    try {
      const tx = await logExpense(expenseInput.trim(), selectedCategory ?? undefined);
      setTransactions((prev) => [tx, ...prev]);
      setExpenseInput("");
      setSelectedCategory(null);
      setSheetVisible(false);
      loadData();
    } finally {
      setLogging(false);
    }
  };

  const handleDeleteTransaction = async (id: number) => {
    await deleteTransaction(id);
    setTransactions((prev) => prev.filter((t) => t.id !== id));
    loadData();
  };

  const openBudgetEdit = (category: string) => {
    const existing = budgets.find((b) => b.category.toLowerCase() === category.toLowerCase());
    setBudgetInput(existing ? String(existing.amount) : "");
    setEditingCategory(category);
    setBudgetModalVisible(true);
  };

  const handleSaveBudget = async () => {
    if (!editingCategory) return;
    const amount = parseFloat(budgetInput);
    if (isNaN(amount) || amount <= 0) {
      Alert.alert("Invalid amount", "Enter a positive number.");
      return;
    }
    setSavingBudget(true);
    try {
      await setBudget(editingCategory, amount);
      await loadData();
      setBudgetModalVisible(false);
    } finally {
      setSavingBudget(false);
    }
  };

  const formatCurrency = (n: number) =>
    new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(n);

  const monthName = now.toLocaleDateString("en-US", { month: "long" });

  if (loading) {
    return (
      <SafeAreaView style={{ flex: 1, backgroundColor: colors.background }}>
        <View style={styles.center}><ActivityIndicator color={colors.accent} /></View>
      </SafeAreaView>
    );
  }

  if (error) {
    return (
      <SafeAreaView style={{ flex: 1, backgroundColor: colors.background }}>
        <View style={styles.center}>
          <Text style={{ color: colors.accentRed, fontSize: 15, textAlign: "center", padding: 20 }}>{error}</Text>
        </View>
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: colors.background }}>
      <ScrollView
        style={{ flex: 1 }}
        contentContainerStyle={styles.content}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={handleRefresh} />}
      >
        {/* Month spend */}
        {summary && (
          <View style={[styles.card, { backgroundColor: colors.card }]}>
            <Text style={[styles.sectionTitle, { color: colors.text }]}>{monthName} Spending</Text>
            {summary.total_budget != null ? (
              <ProgressBar label="Total" value={summary.total_spent} target={summary.total_budget} unit="" color={colors.accentGreen} formatter={formatCurrency} />
            ) : (
              <Text style={[styles.bigNumber, { color: colors.text }]}>{formatCurrency(summary.total_spent)}</Text>
            )}
          </View>
        )}

        {/* Log Expense CTA */}
        <TouchableOpacity style={[styles.primaryButton, { backgroundColor: colors.accent }]} onPress={() => setSheetVisible(true)}>
          <Text style={styles.primaryButtonText}>+ Log Expense</Text>
        </TouchableOpacity>

        {/* Category breakdown with budget edit */}
        {summary && summary.categories.length > 0 && (
          <View style={[styles.card, { backgroundColor: colors.card }]}>
            <View style={styles.cardHeader}>
              <Text style={[styles.sectionTitle, { color: colors.text }]}>By Category</Text>
              <Text style={[styles.editHint, { color: colors.textTertiary }]}>Tap to set budget</Text>
            </View>
            {summary.categories.map((cat) => (
              <TouchableOpacity key={cat.category} style={[styles.categoryRow, { borderBottomColor: colors.border }]} onPress={() => openBudgetEdit(cat.category)}>
                <Text style={[styles.categoryName, { color: colors.text }]}>{cat.category}</Text>
                <View style={styles.categoryRight}>
                  <Text style={[styles.categoryAmount, cat.over_budget && { color: colors.accentRed }]}>
                    {formatCurrency(cat.spent)}
                    {cat.budget != null && (
                      <Text style={{ color: colors.textSecondary, fontWeight: "400" }}> / {formatCurrency(cat.budget)}</Text>
                    )}
                  </Text>
                  {cat.over_budget && (
                    <View style={[styles.overTag, { backgroundColor: colors.accentRed + "22" }]}>
                      <Text style={[styles.overTagText, { color: colors.accentRed }]}>OVER</Text>
                    </View>
                  )}
                  <Text style={{ color: colors.textTertiary, fontSize: 12 }}>›</Text>
                </View>
              </TouchableOpacity>
            ))}
          </View>
        )}

        {/* Budget limits section */}
        {budgets.length > 0 && (
          <View style={[styles.card, { backgroundColor: colors.card }]}>
            <Text style={[styles.sectionTitle, { color: colors.text }]}>Budget Limits</Text>
            {budgets.map((b) => (
              <TouchableOpacity key={b.id} style={[styles.categoryRow, { borderBottomColor: colors.border }]} onPress={() => openBudgetEdit(b.category)}>
                <Text style={[styles.categoryName, { color: colors.text }]}>{b.category}</Text>
                <Text style={[styles.categoryAmount, { color: colors.textSecondary }]}>{formatCurrency(b.amount)}/mo</Text>
              </TouchableOpacity>
            ))}
          </View>
        )}

        {/* Net worth */}
        {netWorth && (
          <View style={[styles.card, { backgroundColor: colors.card }]}>
            <Text style={[styles.sectionTitle, { color: colors.text }]}>Net Worth</Text>
            <Text style={[styles.bigNumber, { color: colors.text }]}>{formatCurrency(netWorth.total)}</Text>
            <Text style={[styles.netWorthNote, { color: colors.textSecondary }]}>
              As of {new Date(netWorth.snapshot_date).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" })} · Manual snapshots only
            </Text>
          </View>
        )}

        {/* Savings goals */}
        {goals.length > 0 && (
          <View style={[styles.card, { backgroundColor: colors.card }]}>
            <Text style={[styles.sectionTitle, { color: colors.text }]}>Savings Goals</Text>
            {goals.map((goal) => (
              <View key={goal.id} style={styles.goalRow}>
                <ProgressBar label={goal.name} value={goal.current_amount} target={goal.target_amount} unit="" color={colors.accentGreen} formatter={formatCurrency} />
              </View>
            ))}
          </View>
        )}

        {/* Recent transactions with swipe delete */}
        <View style={styles.section}>
          <Text style={[styles.sectionTitle, { color: colors.text }]}>Recent Transactions</Text>
          {transactions.length === 0 && (
            <Text style={{ color: colors.textSecondary, fontSize: 14 }}>No transactions yet.</Text>
          )}
          {transactions.map((tx) => (
            <TransactionRow key={tx.id} transaction={tx} onDelete={handleDeleteTransaction} />
          ))}
        </View>
      </ScrollView>

      {/* Log Expense Sheet */}
      <Modal visible={sheetVisible} transparent animationType="slide" onRequestClose={() => setSheetVisible(false)}>
        <KeyboardAvoidingView behavior={Platform.OS === "ios" ? "padding" : undefined} style={styles.modalOverlay}>
          <View style={[styles.modalSheet, { backgroundColor: colors.card }]}>
            <Text style={[styles.modalTitle, { color: colors.text }]}>Log an Expense</Text>

            {/* Category picker */}
            <Text style={[styles.pickerLabel, { color: colors.textSecondary }]}>Category (optional)</Text>
            <ScrollView horizontal showsHorizontalScrollIndicator={false} style={styles.categoryPicker} contentContainerStyle={styles.categoryPickerContent}>
              {EXPENSE_CATEGORIES.map((cat) => (
                <TouchableOpacity
                  key={cat}
                  style={[
                    styles.categoryPill,
                    { backgroundColor: selectedCategory === cat ? colors.accent : colors.cardElevated },
                  ]}
                  onPress={() => setSelectedCategory(selectedCategory === cat ? null : cat)}
                >
                  <Text style={[styles.categoryPillText, { color: selectedCategory === cat ? "#fff" : colors.textSecondary }]}>
                    {cat}
                  </Text>
                </TouchableOpacity>
              ))}
            </ScrollView>

            <TextInput
              style={[styles.textInput, { backgroundColor: colors.inputBg, color: colors.text }]}
              value={expenseInput}
              onChangeText={setExpenseInput}
              placeholder="e.g. $45 at Whole Foods"
              placeholderTextColor={colors.textTertiary}
              multiline
              autoFocus
            />
            <TouchableOpacity
              style={[styles.submitButton, { backgroundColor: colors.accent }, logging && styles.buttonDisabled]}
              onPress={handleLogExpense}
              disabled={logging}
            >
              {logging ? <ActivityIndicator color="#fff" /> : <Text style={styles.submitText}>Log Expense</Text>}
            </TouchableOpacity>
            <TouchableOpacity style={styles.cancelButton} onPress={() => setSheetVisible(false)}>
              <Text style={[styles.cancelText, { color: colors.textSecondary }]}>Cancel</Text>
            </TouchableOpacity>
          </View>
        </KeyboardAvoidingView>
      </Modal>

      {/* Budget Edit Modal */}
      <Modal visible={budgetModalVisible} transparent animationType="slide" onRequestClose={() => setBudgetModalVisible(false)}>
        <KeyboardAvoidingView behavior={Platform.OS === "ios" ? "padding" : undefined} style={styles.modalOverlay}>
          <View style={[styles.modalSheet, { backgroundColor: colors.card }]}>
            <Text style={[styles.modalTitle, { color: colors.text }]}>
              Budget — {editingCategory}
            </Text>
            <Text style={[styles.pickerLabel, { color: colors.textSecondary }]}>Monthly limit ($)</Text>
            <TextInput
              style={[styles.textInput, { backgroundColor: colors.inputBg, color: colors.text, minHeight: 0 }]}
              value={budgetInput}
              onChangeText={setBudgetInput}
              placeholder="e.g. 500"
              placeholderTextColor={colors.textTertiary}
              keyboardType="decimal-pad"
              autoFocus
            />
            <TouchableOpacity
              style={[styles.submitButton, { backgroundColor: colors.accent }, savingBudget && styles.buttonDisabled]}
              onPress={handleSaveBudget}
              disabled={savingBudget}
            >
              {savingBudget ? <ActivityIndicator color="#fff" /> : <Text style={styles.submitText}>Save Limit</Text>}
            </TouchableOpacity>
            <TouchableOpacity style={styles.cancelButton} onPress={() => setBudgetModalVisible(false)}>
              <Text style={[styles.cancelText, { color: colors.textSecondary }]}>Cancel</Text>
            </TouchableOpacity>
          </View>
        </KeyboardAvoidingView>
      </Modal>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  center: { flex: 1, alignItems: "center", justifyContent: "center" },
  content: { padding: 16, paddingBottom: 40 },
  card: { borderRadius: 12, padding: 16, marginBottom: 16 },
  cardHeader: { flexDirection: "row", justifyContent: "space-between", alignItems: "center", marginBottom: 12 },
  section: { marginBottom: 20 },
  sectionTitle: { fontSize: 15, fontWeight: "600", marginBottom: 12 },
  editHint: { fontSize: 11 },
  bigNumber: { fontSize: 28, fontWeight: "700", marginBottom: 4 },
  netWorthNote: { fontSize: 12 },
  primaryButton: { borderRadius: 12, paddingVertical: 14, alignItems: "center", marginBottom: 16 },
  primaryButtonText: { color: "#fff", fontSize: 16, fontWeight: "600" },
  categoryRow: { flexDirection: "row", justifyContent: "space-between", alignItems: "center", paddingVertical: 10, borderBottomWidth: StyleSheet.hairlineWidth },
  categoryRight: { flexDirection: "row", alignItems: "center", gap: 8 },
  categoryName: { fontSize: 14, flex: 1 },
  categoryAmount: { fontSize: 14, fontWeight: "500" },
  overTag: { borderRadius: 4, paddingHorizontal: 5, paddingVertical: 2 },
  overTagText: { fontSize: 10, fontWeight: "700" },
  goalRow: { marginBottom: 4 },
  // Modal
  modalOverlay: { flex: 1, backgroundColor: "#00000088", justifyContent: "flex-end" },
  modalSheet: { borderTopLeftRadius: 20, borderTopRightRadius: 20, padding: 24, paddingBottom: 40 },
  modalTitle: { fontSize: 17, fontWeight: "600", marginBottom: 16 },
  pickerLabel: { fontSize: 12, fontWeight: "500", marginBottom: 8, textTransform: "uppercase", letterSpacing: 0.5 },
  categoryPicker: { marginBottom: 16 },
  categoryPickerContent: { gap: 8, paddingRight: 16 },
  categoryPill: { borderRadius: 20, paddingHorizontal: 14, paddingVertical: 8 },
  categoryPillText: { fontSize: 14, fontWeight: "500" },
  textInput: { borderRadius: 10, padding: 14, fontSize: 15, minHeight: 80, textAlignVertical: "top", marginBottom: 16 },
  submitButton: { borderRadius: 12, paddingVertical: 14, alignItems: "center", marginBottom: 10 },
  buttonDisabled: { opacity: 0.6 },
  submitText: { color: "#fff", fontSize: 16, fontWeight: "600" },
  cancelButton: { alignItems: "center", paddingVertical: 10 },
  cancelText: { fontSize: 15 },
});
```

- [ ] **Step 3: Commit**

```bash
cd ~/deep-workspace/chitiyu-pi/app
git add components/TransactionRow.tsx app/\(tabs\)/finance.tsx
git commit -m "feat(finance): swipe delete, budget edit, category picker, theme"
```

---

### Task 8: Remaining Tabs + Layout Theme

**Files:**
- Modify: `app/app/(tabs)/tasks.tsx`
- Modify: `app/app/(tabs)/knowledge.tsx`
- Modify: `app/app/_layout.tsx`
- Modify: `app/components/TaskRow.tsx`
- Modify: `app/components/ProgressBar.tsx`
- Modify: `app/components/MacroRings.tsx`

**Goal:** Replace hardcoded colors with theme tokens in remaining files so light mode works everywhere.

- [ ] **Step 1: Update TaskRow.tsx**

Replace hardcoded colors with theme-aware versions. TaskRow already uses `Animated`/`PanResponder` so we just swap color literals:

```typescript
// Add to imports:
import { useTheme } from "../lib/theme";

// Inside TaskRow function, add:
const { colors } = useTheme();

// Replace style references:
// styles.row backgroundColor "#000" → colors.background
// styles.checkCircle borderColor "#636366" → colors.checkCircle
// styles.deleteBackground backgroundColor "#FF453A" → colors.swipeDelete
// styles.title color "#fff" → colors.text
// styles.due color "#8E8E93" → colors.textSecondary
// styles.row borderBottomColor "#2C2C2E" → colors.border
```

Full rewrite of TaskRow.tsx:

```typescript
import React, { useRef } from "react";
import { View, Text, TouchableOpacity, Animated, PanResponder, StyleSheet } from "react-native";
import type { Task } from "../lib/api";
import { useTheme } from "../lib/theme";

interface Props {
  task: Task;
  onComplete: (id: number) => void;
  onDelete: (id: number) => void;
}

const SWIPE_THRESHOLD = -80;

export function TaskRow({ task, onComplete, onDelete }: Props) {
  const { colors } = useTheme();
  const translateX = useRef(new Animated.Value(0)).current;
  const deleteOpacity = translateX.interpolate({
    inputRange: [SWIPE_THRESHOLD, 0],
    outputRange: [1, 0],
    extrapolate: "clamp",
  });

  const panResponder = PanResponder.create({
    onMoveShouldSetPanResponder: (_, { dx }) => Math.abs(dx) > 10,
    onPanResponderMove: (_, { dx }) => { if (dx < 0) translateX.setValue(dx); },
    onPanResponderRelease: (_, { dx }) => {
      if (dx < SWIPE_THRESHOLD) {
        Animated.timing(translateX, { toValue: -120, duration: 150, useNativeDriver: true }).start(
          () => onDelete(task.id)
        );
      } else {
        Animated.spring(translateX, { toValue: 0, useNativeDriver: true }).start();
      }
    },
  });

  return (
    <View style={styles.container}>
      <Animated.View style={[styles.deleteBackground, { opacity: deleteOpacity, backgroundColor: colors.swipeDelete }]}>
        <Text style={styles.deleteLabel}>Delete</Text>
      </Animated.View>
      <Animated.View
        style={[styles.row, { transform: [{ translateX }], backgroundColor: colors.background, borderBottomColor: colors.border }]}
        {...panResponder.panHandlers}
      >
        <TouchableOpacity style={styles.checkbox} onPress={() => onComplete(task.id)} hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}>
          <View style={[styles.checkCircle, { borderColor: colors.checkCircle }]} />
        </TouchableOpacity>
        <View style={styles.info}>
          <Text style={[styles.title, { color: colors.text }]}>{task.title}</Text>
          {task.due_at && (
            <Text style={[styles.due, { color: colors.textSecondary }]}>
              Due {new Date(task.due_at).toLocaleDateString("en-US", { month: "short", day: "numeric" })}
            </Text>
          )}
        </View>
      </Animated.View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { position: "relative", overflow: "hidden" },
  deleteBackground: { position: "absolute", right: 0, top: 0, bottom: 0, width: 120, alignItems: "center", justifyContent: "center" },
  deleteLabel: { color: "#fff", fontWeight: "600", fontSize: 14 },
  row: { flexDirection: "row", alignItems: "center", paddingVertical: 12, paddingHorizontal: 4, borderBottomWidth: StyleSheet.hairlineWidth },
  checkbox: { marginRight: 12 },
  checkCircle: { width: 22, height: 22, borderRadius: 11, borderWidth: 2 },
  info: { flex: 1 },
  title: { fontSize: 15 },
  due: { fontSize: 12, marginTop: 2 },
});
```

- [ ] **Step 2: Update tasks.tsx with theme colors**

Add `import { useTheme } from "../../lib/theme";` and `const { colors } = useTheme();` inside the component. Replace all hardcoded colors:

- `backgroundColor: "#000"` → `colors.background`
- `backgroundColor: "#1C1C1E"` → `colors.card`
- `backgroundColor: "#2C2C2E"` → `colors.cardElevated`
- `color: "#fff"` → `colors.text`
- `color: "#8E8E93"` → `colors.textSecondary`
- `color: "#636366"` → `colors.textTertiary`
- `color: "#007AFF"` → `colors.accent`
- `color: "#FF453A"` → `colors.accentRed`
- `backgroundColor: "#1C0A0A"` → `colors.overdueStripe`
- `borderLeftColor: "#FF453A"` → `colors.accentRed`
- `borderBottomColor: "#2C2C2E"` → `colors.border`

Since tasks.tsx uses `StyleSheet.create` with static values, switch to inline styles for color-dependent properties, keeping the StyleSheet for layout/size properties. Pattern: `style={[styles.safe, { backgroundColor: colors.background }]}`.

- [ ] **Step 3: Update knowledge.tsx with theme colors**

Same approach as tasks.tsx — add useTheme, replace hardcoded colors inline. Key replacements:
- `backgroundColor: "#000"` → `colors.background`
- `backgroundColor: "#1C1C1E"` → `colors.card`
- `backgroundColor: "#2C2C2E"` → `colors.inputBg`
- `color: "#fff"` → `colors.text`
- `color: "#8E8E93"` → `colors.textSecondary`
- `color: "#636366"` → `colors.textTertiary`
- `color: "#007AFF"` → `colors.accent`
- `borderBottomColor: "#2C2C2E"` → `colors.border`
- `backgroundColor: "#007AFF"` (saveFact button) → `colors.accent`

- [ ] **Step 4: Update _layout.tsx with theme colors**

```typescript
import { Tabs } from "expo-router";
import { Ionicons } from "@expo/vector-icons";
import { useTheme } from "../../lib/theme";

type IoniconsName = React.ComponentProps<typeof Ionicons>["name"];

interface TabConfig {
  name: string;
  title: string;
  icon: IoniconsName;
  activeIcon: IoniconsName;
}

const TABS: TabConfig[] = [
  { name: "index", title: "Insights", icon: "bulb-outline", activeIcon: "bulb" },
  { name: "health", title: "Health", icon: "heart-outline", activeIcon: "heart" },
  { name: "finance", title: "Finance", icon: "wallet-outline", activeIcon: "wallet" },
  { name: "tasks", title: "Tasks", icon: "checkbox-outline", activeIcon: "checkbox" },
  { name: "knowledge", title: "Knowledge", icon: "library-outline", activeIcon: "library" },
];

export default function RootLayout() {
  const { colors } = useTheme();
  return (
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
  );
}
```

- [ ] **Step 5: Update ProgressBar.tsx with theme**

```typescript
import React from "react";
import { View, Text, StyleSheet } from "react-native";
import { useTheme } from "../lib/theme";

interface Props {
  label: string;
  value: number;
  target: number;
  unit: string;
  color?: string;
  formatter?: (n: number) => string;
}

export function ProgressBar({ label, value, target, unit, color, formatter }: Props) {
  const { colors } = useTheme();
  const trackColor = color ?? colors.accent;
  const pct = target > 0 ? Math.min(value / target, 1) : 0;
  const over = value > target;
  const fmt = formatter ?? ((n: number) => `${Math.round(n)}${unit}`);

  return (
    <View style={styles.container}>
      <View style={styles.labelRow}>
        <Text style={[styles.label, { color: colors.textSecondary }]}>{label}</Text>
        <Text style={[styles.value, { color: over ? colors.accentRed : colors.text }]}>
          {fmt(value)}
          <Text style={{ color: colors.textSecondary, fontWeight: "400" }}> / {fmt(target)}</Text>
        </Text>
      </View>
      <View style={[styles.track, { backgroundColor: colors.border }]}>
        <View style={[styles.fill, { width: `${pct * 100}%` as `${number}%`, backgroundColor: over ? colors.accentRed : trackColor }]} />
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { marginBottom: 14 },
  labelRow: { flexDirection: "row", justifyContent: "space-between", marginBottom: 5 },
  label: { fontSize: 13 },
  value: { fontSize: 13, fontWeight: "600" },
  track: { height: 6, borderRadius: 3, overflow: "hidden" },
  fill: { height: "100%", borderRadius: 3 },
});
```

- [ ] **Step 6: Update MacroRings.tsx with theme**

```typescript
import React from "react";
import { View, Text, StyleSheet } from "react-native";
import type { MealTotals } from "../lib/api";
import { TARGETS } from "../constants/targets";
import { useTheme } from "../lib/theme";

interface Props { totals: MealTotals; }

export function MacroRings({ totals }: Props) {
  const { colors } = useTheme();
  const rings = [
    { label: "Protein", value: totals.protein, target: TARGETS.protein, color: colors.accentGreen },
    { label: "Fat", value: totals.fat, target: TARGETS.fat, color: colors.accentOrange },
    { label: "Carbs", value: totals.carbs, target: TARGETS.carbs, color: colors.accentPurple },
  ];

  return (
    <View style={styles.row}>
      {rings.map((ring) => {
        const pct = Math.min(ring.value / ring.target, 1);
        const over = ring.value > ring.target;
        return (
          <View key={ring.label} style={styles.ring}>
            <View style={[styles.circle, { borderColor: over ? colors.accentRed : ring.color, backgroundColor: colors.cardElevated }]}>
              <View style={[styles.fill, { height: `${pct * 100}%` as `${number}%`, backgroundColor: over ? colors.accentRed + "33" : ring.color + "33" }]} />
            </View>
            <Text style={[styles.value, { color: colors.text }]}>{Math.round(ring.value)}g</Text>
            <Text style={[styles.label, { color: colors.textSecondary }]}>{ring.label}</Text>
          </View>
        );
      })}
    </View>
  );
}

const styles = StyleSheet.create({
  row: { flexDirection: "row", justifyContent: "space-around", marginBottom: 20 },
  ring: { alignItems: "center", gap: 4 },
  circle: { width: 72, height: 72, borderRadius: 36, borderWidth: 3, overflow: "hidden", justifyContent: "flex-end" },
  fill: { width: "100%" },
  value: { fontSize: 14, fontWeight: "600" },
  label: { fontSize: 11 },
});
```

- [ ] **Step 7: Commit**

```bash
cd ~/deep-workspace/chitiyu-pi/app
git add components/TaskRow.tsx components/ProgressBar.tsx components/MacroRings.tsx \
        app/\(tabs\)/tasks.tsx app/\(tabs\)/knowledge.tsx app/_layout.tsx
git commit -m "feat(theme): apply dark/light theme to all remaining tabs and components"
```

---

### Task 9: Run Full Test Suite

**Files:** No changes — verification only.

- [ ] **Step 1: Run all backend tests**

```bash
cd ~/deep-workspace/chitiyu-pi && python -m pytest tests/ -v 2>&1 | tail -50
```

Expected: all tests pass.

- [ ] **Step 2: TypeScript check (optional, if tsc available)**

```bash
cd ~/deep-workspace/chitiyu-pi/app && npx tsc --noEmit 2>&1 | head -40
```

Expected: no type errors.

- [ ] **Step 3: Verify backend is running and key endpoints respond**

```bash
curl -s -X GET "http://10.0.0.179:8000/health/recipes" -H "X-Api-Key: chitiyu-2026" | python3 -m json.tool | head -10
curl -s -X POST "http://10.0.0.179:8000/health/meals/preview" -H "X-Api-Key: chitiyu-2026" -H "Content-Type: application/json" -d '{"text": "oatmeal with banana"}' | python3 -m json.tool
curl -s -X GET "http://10.0.0.179:8000/finance/budgets" -H "X-Api-Key: chitiyu-2026" | python3 -m json.tool | head -10
```

Expected: JSON responses, no 500 errors.

- [ ] **Step 4: Final commit if any fixups needed, then report ready**
