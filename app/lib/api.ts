import { API_KEY, API_URL } from "./auth";

// ─── Shared ──────────────────────────────────────────────────────────────────

async function request<T>(
  method: "GET" | "POST" | "PATCH" | "DELETE",
  path: string,
  body?: unknown
): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, {
    method,
    headers: {
      "Content-Type": "application/json",
      "X-Api-Key": API_KEY,
    },
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
  if (!response.ok) {
    const text = await response.text();
    throw new Error(`${method} ${path} → ${response.status}: ${text}`);
  }
  return response.json() as T;
}

// ─── Insights ─────────────────────────────────────────────────────────────────
// Backend: GET /insights/latest returns {scope, cards_json, generated_at, cards}
//          where cards is a parsed JSON array of card objects.
//          POST /insights/generate returns {status: "generating", scope} — NOT cards.
//          generateInsights() fires the trigger then fetches latest; callers always
//          use getInsightsLatest() to read cards.

export interface InsightCard {
  title: string;
  fact: string;
  why: string;
  action: string;
}

export interface InsightsLatestResponse {
  scope: "today" | "week";
  cards_json: string;         // raw JSON string — use `cards` field instead
  cards: InsightCard[];       // parsed array, ready to render
  generated_at: string;
}

export interface GenerateResponse {
  status: string;
  scope: string;
}

export const getInsightsLatest = (scope: "today" | "week" = "today") =>
  request<InsightsLatestResponse>("GET", `/insights/latest?scope=${scope}`);

export const generateInsights = (scope: "today" | "week") =>
  request<GenerateResponse>("POST", "/insights/generate", { scope });

// ─── Health ───────────────────────────────────────────────────────────────────

export interface Meal {
  id: number;
  logged_at: string;
  description: string;
  calories: number;
  protein: number;
  fat: number;
  carbs: number;
}

export interface MealTotals {
  calories: number;
  protein: number;
  fat: number;
  carbs: number;
}

export interface MealsResponse {
  meals: Meal[];
  totals: MealTotals;
}

export interface HealthMetrics {
  date: string;
  steps: number | null;
  sleep_deep_mins: number | null;
  sleep_total_mins: number | null;
  resting_hr: number | null;
}

export const getMealsToday = () =>
  request<MealsResponse>("GET", "/health/meals/today");

// POST /health/meals returns {"result": str} — an NL confirmation string, not a Meal.
// After logging, reload getMealsToday() to get updated meals + totals.
export interface LogMealResponse { result: string; }
export const logMeal = (text: string) =>
  request<LogMealResponse>("POST", "/health/meals", { text });

export const getHealthMetricsToday = () =>
  request<HealthMetrics>("GET", "/health/metrics/today");

// ─── Finance ──────────────────────────────────────────────────────────────────

export interface Transaction {
  id: number;
  date: string;
  amount: number;
  category: string;
  description: string;
  source: "manual" | "csv";
}

export interface CategoryBudget {
  category: string;
  spent: number;
  budget: number | null;
  over_budget: boolean;
}

export interface FinanceSummary {
  year: number;
  month: number;
  total_spent: number;      // sum of all negative (expense) transactions
  total_budget: number | null; // sum of all budget rows, null if no budgets set
  categories: CategoryBudget[];
}

export interface NetWorth {
  snapshot_date: string;
  assets_json: Record<string, number>;
  liabilities_json: Record<string, number>;
  total: number;
}

export interface SavingsGoal {
  id: number;
  name: string;
  target_amount: number;
  current_amount: number;
  target_date: string | null;
}

export const getFinanceSummary = (year: number, month: number) =>
  request<FinanceSummary>("GET", `/finance/summary/${year}/${month}`);

export const getTransactions = () =>
  request<{ transactions: Transaction[] }>("GET", "/finance/transactions");

export const logExpense = (text: string) =>
  request<Transaction>("POST", "/finance/transactions", { text });

export const getNetWorth = () =>
  request<NetWorth | null>("GET", "/finance/networth").catch((e) => {
    // 404 means no snapshot recorded yet — treat as null, not an error
    if (e instanceof Error && e.message.includes("404")) return null;
    throw e;
  });

export const getSavingsGoals = () =>
  request<{ goals: SavingsGoal[] }>("GET", "/finance/goals");

// ─── Tasks ────────────────────────────────────────────────────────────────────

export interface Task {
  id: number;
  title: string;
  due_at: string | null;
  completed_at: string | null;
  priority: string | null;
  tags: string[];
}

// GET /tasks/overdue and /tasks/today return plain Task[] arrays (no wrapper object).
export const getTasksOverdue = () =>
  request<Task[]>("GET", "/tasks/overdue");

export const getTasksToday = () =>
  request<Task[]>("GET", "/tasks/today");

export const addTask = (title: string) =>
  request<Task>("POST", "/tasks/", { title });

export const completeTask = (id: number) =>
  request<Task>("PATCH", `/tasks/${id}/complete`, {});

export const deleteTask = (id: number) =>
  request<void>("DELETE", `/tasks/${id}`);

// ─── Knowledge ────────────────────────────────────────────────────────────────

export interface KnowledgeEntity {
  id: number;
  name: string;
  type: string;
  fact_count?: number; // backend does not return this field — default to 0 when rendering
}

export interface KnowledgeFact {
  id: number;
  entity_id: number;
  entity_name: string;
  content: string;
  created_at: string;
}

// GET /knowledge/search returns a plain KnowledgeFact[] array (no wrapper).
// GET /knowledge/entities returns a plain KnowledgeEntity[] array (no wrapper).
//   KnowledgeEntity from backend has no fact_count field — use 0 as default.
// POST /knowledge/facts returns {"result": str} — NL confirmation, not a KnowledgeFact.
export interface SaveFactResponse { result: string; }
export const searchKnowledge = (q: string) =>
  request<KnowledgeFact[]>("GET", `/knowledge/search?q=${encodeURIComponent(q)}`);

export const saveFact = (text: string) =>
  request<SaveFactResponse>("POST", "/knowledge/facts", { text });

export const getEntities = () =>
  request<KnowledgeEntity[]>("GET", "/knowledge/entities");
