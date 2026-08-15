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

// Backend returns { meals, metrics, summary } — no totals key. Totals are summed client-side.
export interface MealsResponse {
  meals: Meal[];
  metrics: HealthMetrics | null;
  summary: string;
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

export const getMealsForDate = (date: string) =>
  request<MealsResponse>("GET", `/health/summary/${date}`);

// POST /health/meals returns {"result": str} — an NL confirmation string, not a Meal.
// After logging, reload getMealsToday() to get updated meals + totals.
export interface LogMealResponse { result: string; }
export const logMeal = (text: string) =>
  request<LogMealResponse>("POST", "/health/meals", { text });

export const getHealthMetricsToday = () =>
  request<HealthMetrics>("GET", "/health/metrics/today");

export const syncHealthMetrics = (date: string, steps?: number, sleepTotalMins?: number, sleepDeepMins?: number, restingHr?: number) =>
  request<{ ok: boolean }>("POST", "/health/sync", {
    date,
    steps: steps ?? null,
    sleep_total_mins: sleepTotalMins ?? null,
    sleep_deep_mins: sleepDeepMins ?? null,
    resting_hr: restingHr ?? null,
  });

// ─── Health — Weight ──────────────────────────────────────────────────────────

export interface WeightLog {
  date: string;
  weight_kg: number;
  weight_lbs: number;  // computed by backend: weight_kg * 2.20462, rounded to 1dp
  bodyfat_pct: number | null;
  muscle_kg: number | null;
  bmi: number | null;
  source: string;
}

export interface WeightTrend {
  logs: WeightLog[];
  avg_weight_kg: number | null;
  delta_kg: number | null;
}

export const getWeightLatest = () =>
  request<WeightLog | Record<string, never>>("GET", "/health/weight/latest");

export const getWeightTrend = (days = 7) =>
  request<WeightTrend>("GET", `/health/weight/trend?days=${days}`);

// ─── Health — additional ──────────────────────────────────────────────────────

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

export const logMealFromRecipe = (recipeId: number, loggedAt?: string) =>
  request<{ result: string }>("POST", "/health/meals/from-recipe", { recipe_id: recipeId, logged_at: loggedAt ?? null });

export const logMealParsed = (data: MealPreviewResult, loggedAt?: string) =>
  request<LogMealResponse>("POST", "/health/meals/log-parsed", {
    description: data.description,
    calories: data.calories,
    protein: data.protein,
    fat: data.fat ?? null,
    carbs: data.carbs ?? null,
    logged_at: loggedAt ?? null,
  });

export const getRecipes = () =>
  request<Recipe[]>("GET", "/health/recipes");

export const createRecipe = (name: string, calories: number, protein: number, fat?: number, carbs?: number) =>
  request<{ id: number; name: string }>("POST", "/health/recipes", { name, calories, protein, fat, carbs });

export const deleteRecipe = (id: number) =>
  request<{ ok: boolean }>("DELETE", `/health/recipes/${id}`);

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
  budget_type: "fixed" | "recurring" | "discretionary" | "envelope";
  period: "monthly" | "biannual" | "annual" | "weekly";
  over_budget: boolean;
  is_excluded: boolean;
}

export interface Milestone {
  id: number;
  period_label: string;
  target_date: string;
  expected_net_worth: number;
  actual_net_worth: number | null;
  note: string | null;
  current_balance: number | null;
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

export const logExpense = (text: string, category?: string) =>
  request<Transaction>("POST", "/finance/transactions", { text, ...(category ? { category } : {}) });

export const getSavingsGoals = () =>
  request<{ goals: SavingsGoal[] }>("GET", "/finance/goals");

export const createGoal = (m: Omit<SavingsGoal, "id" | "current_amount">) =>
  request<SavingsGoal>("POST", "/finance/goals", m);

export const deleteTransaction = (id: number) =>
  request<{ ok: boolean }>("DELETE", `/finance/transactions/${id}`);

export interface Budget {
  id: number;
  category: string;
  amount: number;
  period: "monthly" | "biannual" | "annual" | "weekly";
  budget_type: "fixed" | "recurring" | "discretionary" | "envelope";
}

export const getBudgets = () =>
  request<Budget[]>("GET", "/finance/budgets");

export const setBudget = (category: string, amount: number) =>
  request<Budget>("POST", "/finance/budgets", { category, amount });

export const setBudgetWithType = (
  category: string,
  amount: number,
  budget_type: Budget["budget_type"],
  period: Budget["period"] = "monthly"
) =>
  request<Budget>("POST", "/finance/budgets", { category, amount, budget_type, period });

export const deleteBudget = (id: number) =>
  request<{ ok: boolean }>("DELETE", `/finance/budgets/${id}`);

export const patchMilestoneActual = (target_date: string, actual_net_worth: number) =>
  request<{ target_date: string; actual_net_worth: number }>(
    "PATCH", `/finance/milestones/${target_date}`, { actual_net_worth }
  );

// ─── Accounts ─────────────────────────────────────────────────────────────────

export interface Account {
  id: number;
  name: string;
  type: "checking" | "savings" | "investment" | "credit" | "brokerage" | "crypto";
  currency: string;
}

export const getAccounts = () =>
  request<{ accounts: Account[] }>("GET", "/finance/accounts");

export const createAccount = (name: string, type: Account["type"]) =>
  request<Account>("POST", "/finance/accounts", { name, type });

// ─── Account Balances ─────────────────────────────────────────────────────────

export interface AccountBalance {
  id: number;
  account_id: number;
  account_name: string;
  account_type: string;
  date: string;
  balance: number;
  note: string | null;
}

export interface BalanceEntry {
  account_id: number;
  balance: number;
  note?: string;
}

export const getLatestBalances = () =>
  request<{ balances: AccountBalance[]; computed_net_worth: number | null }>(
    "GET", "/finance/balances/latest"
  );

export const updateBalances = (balances: BalanceEntry[], date?: string) =>
  request<{ updated: any[]; computed_net_worth: number | null }>(
    "POST", "/finance/balances",
    { balances, ...(date ? { date } : {}) }
  );

// ─── Financial Milestones ─────────────────────────────────────────────────────

export interface FinancialMilestone {
  id: number;
  period_label: string;
  target_date: string;
  expected_net_worth: number;
  actual_net_worth: number | null;
  note: string | null;
  current_balance: number | null;
}

export const getMilestones = (period_label?: string) =>
  request<{ periods: string[]; milestones: FinancialMilestone[] }>(
    "GET", `/finance/milestones${period_label ? `?period_label=${period_label}` : ""}`
  );

export const createMilestone = (m: Omit<FinancialMilestone, "id">) =>
  request<{ id: number }>("POST", "/finance/milestones", m);

// ─── Tasks ────────────────────────────────────────────────────────────────────

export interface Task {
  id: number;
  uid?: string;
  title: string;
  due_at: string | null;
  completed_at: string | null;
  priority: number;
  tags: string[];
  is_recurring?: boolean;
}

export interface TaskTemplate {
  id: number;
  title: string;
  recurrence: "daily" | "weekly" | "monthly" | "yearly";
  anchor_date: string;
  advance_days: number;
  priority: number;
}

export const getTasksOverdue = () =>
  request<Task[]>("GET", "/tasks/overdue");

export const getTasksToday = () =>
  request<Task[]>("GET", "/tasks/today");

export const addTask = (title: string, due_at?: string, priority: number = 0) =>
  request<Task>("POST", "/tasks/", { title, priority, ...(due_at ? { due_at } : {}) });

export const getTasksByDate = (date: string) =>
  request<Task[]>("GET", `/tasks/by-date?date=${encodeURIComponent(date)}`);

export const getTasksAll = () =>
  request<Task[]>("GET", "/tasks/");

export const completeTask = (id: number) =>
  request<{ ok: boolean }>("PATCH", `/tasks/${id}/complete`, {});

export const deleteTask = (id: number) =>
  request<{ ok: boolean }>("DELETE", `/tasks/${id}`);

export const updateTask = (id: number, fields: { title?: string; due_at?: string | null; priority?: number }) =>
  request<{ ok: boolean }>("PATCH", `/tasks/${id}`, fields);

export const getTasksDatesSummary = (start: string, end: string) =>
  request<Record<string, number>>("GET", `/tasks/dates-summary?start=${start}&end=${end}`);

export const createTaskTemplate = (
  title: string,
  recurrence: TaskTemplate["recurrence"],
  anchor_date: string,
  advance_days?: number
) =>
  request<TaskTemplate>("POST", "/tasks/templates", {
    title, recurrence, anchor_date, ...(advance_days !== undefined ? { advance_days } : {})
  });

export const getTaskTemplates = () =>
  request<TaskTemplate[]>("GET", "/tasks/templates");

export const deleteTaskTemplate = (id: number) =>
  request<{ ok: boolean }>("DELETE", `/tasks/templates/${id}`);

export const completeInstance = (id: number) =>
  request<{ ok: boolean }>("PATCH", `/tasks/instances/${id}/complete`, {});

export const deleteInstance = (id: number) =>
  request<{ ok: boolean }>("DELETE", `/tasks/instances/${id}`);

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
  extract: string;
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
