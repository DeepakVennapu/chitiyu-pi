import React, { useState, useEffect, useCallback } from "react";
import { SmartInputSheet } from "../../components/SmartInputSheet";
import {
  View, Text, ScrollView, TouchableOpacity, Modal, TextInput,
  ActivityIndicator, RefreshControl, StyleSheet, SafeAreaView,
  KeyboardAvoidingView, Platform, Alert,
} from "react-native";
import { Accordion } from "../../components/Accordion";
import { ProgressBar } from "../../components/ProgressBar";
import { TransactionRow } from "../../components/TransactionRow";
import {
  getFinanceSummary, getTransactions, logExpense, getSavingsGoals, createGoal,
  deleteTransaction, setBudgetWithType, getAccounts, createAccount, getLatestBalances,
  updateBalances, getMilestones,
  type CategoryBudget, type Budget, type Transaction, type SavingsGoal,
  type Account, type AccountBalance, type BalanceEntry, type FinancialMilestone,
} from "../../lib/api";
import { useTheme } from "../../lib/theme";
import { todayLocal } from "../../lib/dateUtils";

const EXPENSE_CATEGORIES = ["groceries", "dining", "fuel", "shopping", "misc", "home", "travel", "insurance", "gifts", "other"];

// ── helpers ──────────────────────────────────────────────────────────────────

const fmt = (n: number) =>
  new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 }).format(n);

const fmtFull = (n: number) =>
  new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(n);

function accountTypeOrder(type: string): number {
  return { checking: 0, savings: 1, brokerage: 2, investment: 3, crypto: 4, credit: 5 }[type] ?? 9;
}

function groupBalancesByType(balances: AccountBalance[], accounts: Account[]) {
  const accountMap = Object.fromEntries(accounts.map((a) => [a.id, a]));
  const groups: Record<string, AccountBalance[]> = {};
  for (const b of balances) {
    const type = accountMap[b.account_id]?.type ?? b.account_type;
    if (!groups[type]) groups[type] = [];
    groups[type].push(b);
  }
  return groups;
}

// ── sub-components ────────────────────────────────────────────────────────────

function MilestoneRow({ m }: { m: FinancialMilestone }) {
  const { colors } = useTheme();
  const date = new Date(m.target_date + "T00:00:00");
  const label = date.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
  const hasActual = m.actual_net_worth != null;
  const ahead = hasActual && m.actual_net_worth! >= m.expected_net_worth;
  const isPast = m.target_date <= todayLocal();
  const dotColor = !isPast ? colors.textTertiary : ahead ? colors.accentGreen : colors.accentRed;

  return (
    <View style={ms.row}>
      <View style={[ms.dot, { backgroundColor: dotColor }]} />
      <View style={ms.labels}>
        <Text style={[ms.date, { color: colors.text }]}>{label}</Text>
        <Text style={[ms.expected, { color: colors.textSecondary }]}>
          target {fmt(m.expected_net_worth)}
        </Text>
      </View>
      <View style={ms.right}>
        {hasActual ? (
          <>
            <Text style={[ms.actual, { color: ahead ? colors.accentGreen : colors.accentRed }]}>
              {fmt(m.actual_net_worth!)}
            </Text>
            <Text style={[ms.delta, { color: ahead ? colors.accentGreen : colors.accentRed }]}>
              {ahead ? "+" : ""}{fmt(m.actual_net_worth! - m.expected_net_worth)}
            </Text>
          </>
        ) : (
          <Text style={[ms.pending, { color: colors.textTertiary }]}>—</Text>
        )}
      </View>
    </View>
  );
}

const ms = StyleSheet.create({
  row: { flexDirection: "row", alignItems: "center", paddingVertical: 9, gap: 10 },
  dot: { width: 8, height: 8, borderRadius: 4 },
  labels: { flex: 1 },
  date: { fontSize: 14, fontWeight: "500" },
  expected: { fontSize: 11, marginTop: 1 },
  right: { alignItems: "flex-end" },
  actual: { fontSize: 14, fontWeight: "600" },
  delta: { fontSize: 11, marginTop: 1 },
  pending: { fontSize: 14 },
});

// ── main screen ───────────────────────────────────────────────────────────────

export default function FinanceScreen() {
  const { colors } = useTheme();
  const now = new Date();
  const monthName = now.toLocaleDateString("en-US", { month: "long" });

  const [summary, setSummary] = useState<import("../../lib/api").FinanceSummary | null>(null);
  const [transactions, setTransactions] = useState<Transaction[]>([]);
  const [goals, setGoals] = useState<SavingsGoal[]>([]);
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [balances, setBalances] = useState<AccountBalance[]>([]);
  const [computedNetWorth, setComputedNetWorth] = useState<number | null>(null);
  const [milestones, setMilestones] = useState<FinancialMilestone[]>([]);
  const [milestonePeriods, setMilestonePeriods] = useState<string[]>([]);
  const [selectedPeriod, setSelectedPeriod] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // SmartInputSheet state
  const [smartOpen, setSmartOpen] = useState(false);

  // Log expense modal
  const [sheetVisible, setSheetVisible] = useState(false);
  const [expenseInput, setExpenseInput] = useState("");
  const [selectedCategory, setSelectedCategory] = useState<string | null>(null);
  const [logging, setLogging] = useState(false);

  // Budget edit modal
  const [budgetModalVisible, setBudgetModalVisible] = useState(false);
  const [editingCategory, setEditingCategory] = useState<string | null>(null);
  const [editingSpend, setEditingSpend] = useState<number | null>(null);
  const [editingBudgetType, setEditingBudgetType] = useState<Budget["budget_type"]>("discretionary");
  const [editingPeriod, setEditingPeriod] = useState<Budget["period"]>("monthly");
  const [newCategoryInput, setNewCategoryInput] = useState("");
  const [budgetInput, setBudgetInput] = useState("");
  const [savingBudget, setSavingBudget] = useState(false);

  // Balance update modal
  const [balanceModalVisible, setBalanceModalVisible] = useState(false);
  const [balanceInputs, setBalanceInputs] = useState<Record<number, string>>({});
  const [lastUpdated, setLastUpdated] = useState<Record<number, string>>({});
  const [savingBalances, setSavingBalances] = useState(false);

  // Add Goal modal
  const [goalModalVisible, setGoalModalVisible] = useState(false);
  const [goalNameInput, setGoalNameInput] = useState("");
  const [goalAmountInput, setGoalAmountInput] = useState("");
  const [goalDateInput, setGoalDateInput] = useState("");
  const [savingGoal, setSavingGoal] = useState(false);

  // Add Account modal
  const [accountModalVisible, setAccountModalVisible] = useState(false);
  const [accountNameInput, setAccountNameInput] = useState("");
  const [accountTypeInput, setAccountTypeInput] = useState<Account["type"]>("checking");
  const [savingAccount, setSavingAccount] = useState(false);

  const loadData = useCallback(async () => {
    setError(null);
    try {
      const [sumData, txData, goalsData, accountsData, balancesData, milestonesData] =
        await Promise.all([
          getFinanceSummary(now.getFullYear(), now.getMonth() + 1),
          getTransactions(),
          getSavingsGoals(),
          getAccounts(),
          getLatestBalances(),
          getMilestones(),
        ]);
      setSummary(sumData);
      setTransactions(txData.transactions.slice(0, 20));
      setGoals(goalsData.goals);
      setAccounts(accountsData.accounts);
      setBalances(balancesData.balances);
      setComputedNetWorth(balancesData.computed_net_worth);
      setMilestonePeriods(milestonesData.periods);
      setMilestones(milestonesData.milestones);
    } catch (e: any) {
      setError(e?.message ?? "Failed to load finance data");
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => { loadData(); }, [loadData]);

  useEffect(() => {
    if (milestonePeriods.length > 0 && selectedPeriod === null) {
      setSelectedPeriod(milestonePeriods[0]);
    }
  }, [milestonePeriods]);

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
      await loadData();
    } catch (e: any) {
      Alert.alert("Couldn't log expense", e?.message ?? "Please try again.");
    } finally {
      setLogging(false);
    }
  };

  const handleDeleteTransaction = async (id: number) => {
    try {
      await deleteTransaction(id);
      setTransactions((prev) => prev.filter((t) => t.id !== id));
      await loadData();
    } catch (e: any) {
      Alert.alert("Couldn't delete", e?.message ?? "Please try again.");
    }
  };

  const openBudgetEdit = (category: string) => {
    const catData = summary?.categories.find(
      (c) => c.category.toLowerCase() === category.toLowerCase()
    );
    setBudgetInput(catData?.budget != null ? String(catData.budget) : "");
    setEditingSpend(catData?.spent ?? null);
    setEditingBudgetType(catData?.budget_type ?? "discretionary");
    setEditingPeriod(catData?.period ?? "monthly");
    setEditingCategory(category || null);
    setNewCategoryInput("");
    setBudgetModalVisible(true);
  };

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

  const openBalanceModal = () => {
    const initial: Record<number, string> = {};
    const lastUpd: Record<number, string> = {};
    for (const b of balances) {
      initial[b.account_id] = String(Math.abs(b.balance));
      lastUpd[b.account_id] = b.date;
    }
    setBalanceInputs(initial);
    setLastUpdated(lastUpd);
    setBalanceModalVisible(true);
  };

  const handleSaveBalances = async () => {
    const entries: BalanceEntry[] = [];
    for (const acct of accounts) {
      const raw = balanceInputs[acct.id];
      const hasExisting = balances.some(b => b.account_id === acct.id);
      // Skip only if field is blank AND no prior balance exists
      if ((raw == null || raw.trim() === "") && !hasExisting) continue;
      const val = parseFloat(raw ?? "0") || 0;
      // Credit balances stored as negative internally
      entries.push({ account_id: acct.id, balance: acct.type === "credit" ? -Math.abs(val) : val });
    }
    if (entries.length === 0) { setBalanceModalVisible(false); return; }
    setSavingBalances(true);
    try {
      const res = await updateBalances(entries);
      setComputedNetWorth(res.computed_net_worth);
      await loadData();
      setBalanceModalVisible(false);
    } catch (e: any) {
      Alert.alert("Couldn't save balances", e?.message ?? "Please try again.");
    } finally {
      setSavingBalances(false);
    }
  };

  const handleSaveGoal = async () => {
    const name = goalNameInput.trim();
    const amount = parseFloat(goalAmountInput);
    if (!name) { Alert.alert("Missing name", "Enter a goal name."); return; }
    if (isNaN(amount) || amount <= 0) { Alert.alert("Invalid amount", "Enter a positive amount."); return; }
    setSavingGoal(true);
    try {
      await createGoal({ name, target_amount: amount, target_date: goalDateInput.trim() || undefined });
      setGoalNameInput("");
      setGoalAmountInput("");
      setGoalDateInput("");
      setGoalModalVisible(false);
      await loadData();
    } catch (e: any) {
      Alert.alert("Couldn't save goal", e?.message ?? "Please try again.");
    } finally {
      setSavingGoal(false);
    }
  };

  const handleSaveAccount = async () => {
    const name = accountNameInput.trim();
    if (!name) { Alert.alert("Missing name", "Enter an account name."); return; }
    setSavingAccount(true);
    try {
      await createAccount(name, accountTypeInput);
      setAccountNameInput("");
      setAccountTypeInput("checking");
      setAccountModalVisible(false);
      await loadData();
    } catch (e: any) {
      Alert.alert("Couldn't add account", e?.message ?? "Please try again.");
    } finally {
      setSavingAccount(false);
    }
  };

  // ── derived ──────────────────────────────────────────────────────────────────

  const balanceGroups = groupBalancesByType(balances, accounts);
  const accountMap = Object.fromEntries(accounts.map((a) => [a.id, a]));

  const filteredMilestones = selectedPeriod
    ? milestones.filter((m) => m.period_label === selectedPeriod)
    : milestones;

  // investments = non-credit, non-checking, non-savings
  const investmentTypes = new Set(["brokerage", "investment", "crypto"]);
  const investmentTotal = balances
    .filter((b) => investmentTypes.has(accountMap[b.account_id]?.type ?? ""))
    .reduce((s, b) => s + b.balance, 0);

  // ── loading / error ──────────────────────────────────────────────────────────

  if (loading) {
    return (
      <SafeAreaView style={{ flex: 1, backgroundColor: colors.background }}>
        <View style={s.center}><ActivityIndicator color={colors.accent} /></View>
      </SafeAreaView>
    );
  }
  if (error) {
    return (
      <SafeAreaView style={{ flex: 1, backgroundColor: colors.background }}>
        <View style={s.center}>
          <Text style={{ color: colors.accentRed, fontSize: 15, textAlign: "center", padding: 20 }}>{error}</Text>
        </View>
      </SafeAreaView>
    );
  }

  // ── render ───────────────────────────────────────────────────────────────────

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: colors.background }}>
      <ScrollView
        style={{ flex: 1 }}
        contentContainerStyle={s.content}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={handleRefresh} />}
      >

        {/* ── HERO ───────────────────────────────────────────────────────── */}
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
              const current = ms.current_balance;
              const hasCurrent = current != null;
              const ahead = hasCurrent && current >= target;
              return (
                <View style={s.heroMilestone}>
                  <Text style={[s.heroMilestoneLabel, { color: colors.textSecondary }]}>
                    SAVINGS TARGET · {dateLabel}
                  </Text>
                  {hasCurrent ? (
                    <>
                      <View style={s.heroMilestoneRow}>
                        <Text style={[s.heroMilestoneValue, { color: colors.text }]}>
                          {fmt(current)}
                        </Text>
                        <Text style={[s.heroMilestoneSep, { color: colors.textTertiary }]}>/</Text>
                        <Text style={[s.heroMilestoneTarget, { color: colors.textSecondary }]}>
                          {fmt(target)}
                        </Text>
                      </View>
                      <Text style={[s.heroMilestoneDelta, {
                        color: ahead ? colors.accentGreen : colors.accentRed,
                      }]}>
                        {ahead
                          ? `${fmt(current - target)} ahead ✓`
                          : `${fmt(target - current)} to go`}
                      </Text>
                    </>
                  ) : (
                    <Text style={[s.heroMilestoneValue, { color: colors.text }]}>
                      Target: {fmt(target)}
                    </Text>
                  )}
                </View>
              );
            })()}
          </View>
        )}

        {/* ── ACCOUNTS ────────────────────────────────────────────────────── */}
        <Accordion
          title="Accounts"
          badge={computedNetWorth != null ? fmt(computedNetWorth) : undefined}
          defaultOpen
        >
          {accounts.length === 0 ? (
            <Text style={[s.emptyHint, { color: colors.textSecondary }]}>No accounts yet.</Text>
          ) : (
            [...new Set(accounts.map((a) => a.type))]
              .sort((a, b) => accountTypeOrder(a) - accountTypeOrder(b))
              .map((type) => {
                const typeAccounts = accounts
                  .filter((a) => a.type === type)
                  .sort((a, b) => a.name.localeCompare(b.name));
                return (
                  <View key={type}>
                    <Text style={[s.typeHeader, { color: colors.textTertiary }]}>
                      {type.toUpperCase()}
                    </Text>
                    {typeAccounts.map((acct) => {
                      const bal = balances.find((b) => b.account_id === acct.id);
                      const isCredit = acct.type === "credit";
                      const amount = bal ? Math.abs(bal.balance) : null;
                      return (
                        <View key={acct.id} style={[s.acctRow, { borderBottomColor: colors.border }]}>
                          <Text style={[s.acctName, { color: colors.text }]}>{acct.name}</Text>
                          <Text style={[s.acctBalance, {
                            color: amount == null
                              ? colors.textTertiary
                              : isCredit ? colors.accentRed : colors.text,
                          }]}>
                            {amount == null ? "—" : (isCredit ? "-" : "") + fmt(amount)}
                          </Text>
                        </View>
                      );
                    })}
                  </View>
                );
              })
          )}
          <TouchableOpacity
            style={[s.updateBtn, { borderColor: colors.textTertiary, marginTop: 8 }]}
            onPress={() => setAccountModalVisible(true)}
          >
            <Text style={[s.updateBtnText, { color: colors.textTertiary }]}>+ Add Account</Text>
          </TouchableOpacity>
        </Accordion>

        {/* ── DISCRETIONARY ────────────────────────────────────────────── */}
        <Accordion
          title="Discretionary"
          badge={summary ? `${fmt(summary.discretionary_spent)} spent` : undefined}
          defaultOpen
        >
          {summary && summary.by_type.discretionary.length === 0 && (
            <Text style={[s.emptyHint, { color: colors.textSecondary }]}>No discretionary budgets set.</Text>
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

        {/* ── ENVELOPES (6-month pools) ─────────────────────────────────── */}
        {summary && summary.by_type.envelope.length > 0 && (
          <Accordion
            title="Envelopes (6-month)"
            defaultOpen={false}
            badge={(() => {
              const totalBudget = summary.by_type.envelope.reduce((sum, c) => sum + (c.budget ?? 0), 0);
              const totalSpent = summary.by_type.envelope.reduce((sum, c) => sum + c.spent, 0);
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

        {/* ── FIXED ────────────────────────────────────────────────────── */}
        {summary && summary.by_type.fixed.length > 0 && (
          <Accordion
            title="Fixed"
            defaultOpen={false}
            badge={summary.by_type.fixed.reduce((sum, c) => sum + (c.budget ?? 0), 0) > 0
              ? fmt(summary.by_type.fixed.reduce((sum, c) => sum + (c.budget ?? 0), 0))
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

        {/* ── RECURRING ────────────────────────────────────────────────── */}
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

        {/* ── SAVINGS TIMELINE ────────────────────────────────────────────── */}
        {milestones.length > 0 && (
          <Accordion title="Savings Timeline" defaultOpen={false}>
            {milestonePeriods.length > 1 && (
              <ScrollView horizontal showsHorizontalScrollIndicator={false} style={{ marginBottom: 12 }}>
                <View style={s.pillRow}>
                  {milestonePeriods.map((p) => (
                    <TouchableOpacity
                      key={p}
                      style={[s.pill, { backgroundColor: selectedPeriod === p ? colors.accent : colors.cardElevated }]}
                      onPress={() => setSelectedPeriod(p)}
                    >
                      <Text style={[s.pillText, { color: selectedPeriod === p ? "#fff" : colors.textSecondary }]}>{p}</Text>
                    </TouchableOpacity>
                  ))}
                </View>
              </ScrollView>
            )}
            {filteredMilestones.map((m) => (
              <MilestoneRow key={m.id} m={m} />
            ))}
          </Accordion>
        )}

        {/* ── INVESTMENTS ─────────────────────────────────────────────────── */}
        {investmentTotal > 0 && (
          <Accordion
            title="Investments"
            badge={fmt(investmentTotal)}
            defaultOpen={false}
          >
            {balances
              .filter((b) => investmentTypes.has(accountMap[b.account_id]?.type ?? ""))
              .sort((a, b) => b.balance - a.balance)
              .map((b) => (
                <View key={b.account_id} style={[s.acctRow, { borderBottomColor: colors.border }]}>
                  <Text style={[s.acctName, { color: colors.text }]}>{b.account_name}</Text>
                  <Text style={[s.acctBalance, { color: colors.text }]}>{fmt(b.balance)}</Text>
                </View>
              ))}
          </Accordion>
        )}

        {/* ── SAVINGS GOALS ───────────────────────────────────────────────── */}
        <Accordion title="Savings Goals" defaultOpen={false}>
          {goals.length === 0 && (
            <Text style={[s.emptyHint, { color: colors.textSecondary }]}>No savings goals yet.</Text>
          )}
          {goals.map((goal) => (
            <View key={goal.id} style={{ marginBottom: 4 }}>
              <ProgressBar
                label={goal.name}
                value={goal.current_amount}
                target={goal.target_amount}
                unit=""
                color={colors.accentGreen}
                formatter={fmtFull}
              />
            </View>
          ))}
          <TouchableOpacity
            style={[s.updateBtn, { borderColor: colors.accent, marginTop: 8 }]}
            onPress={() => setGoalModalVisible(true)}
          >
            <Text style={[s.updateBtnText, { color: colors.accent }]}>+ Add Goal</Text>
          </TouchableOpacity>
        </Accordion>

        {/* ── RECENT TRANSACTIONS ──────────────────────────────────────────── */}
        <Accordion title="Recent Transactions" defaultOpen={false}>
          {transactions.length === 0 ? (
            <Text style={{ color: colors.textSecondary, fontSize: 14, paddingVertical: 8 }}>No transactions yet.</Text>
          ) : (
            transactions.map((tx) => (
              <TransactionRow key={tx.id} transaction={tx} onDelete={handleDeleteTransaction} />
            ))
          )}
        </Accordion>

      </ScrollView>

      {/* ── Floating action row ────────────────────────────────────────────── */}
      <View style={[s.fabRow, { backgroundColor: colors.background, borderTopColor: colors.border }]}>
        <TouchableOpacity
          style={[s.fab, { backgroundColor: colors.cardElevated }]}
          onPress={() => setSmartOpen(true)}
        >
          <Text style={[s.fabText, { color: colors.accent }]}>+ Log Expense</Text>
        </TouchableOpacity>
        {accounts.length > 0 && (
          <TouchableOpacity
            style={[s.fab, { backgroundColor: colors.accent }]}
            onPress={openBalanceModal}
          >
            <Text style={[s.fabText, { color: "#fff" }]}>Update Balances</Text>
          </TouchableOpacity>
        )}
      </View>

      {/* ── Log Expense Modal ──────────────────────────────────────────────── */}
      <Modal visible={sheetVisible} transparent animationType="slide" onRequestClose={() => setSheetVisible(false)}>
        <KeyboardAvoidingView behavior={Platform.OS === "ios" ? "padding" : undefined} style={s.overlay}>
          <View style={[s.sheet, { backgroundColor: colors.card }]}>
            <Text style={[s.sheetTitle, { color: colors.text }]}>Log an Expense</Text>
            <Text style={[s.pickerLabel, { color: colors.textSecondary }]}>Category (optional)</Text>
            <ScrollView horizontal showsHorizontalScrollIndicator={false} style={{ marginBottom: 16 }}>
              <View style={s.pillRow}>
                {EXPENSE_CATEGORIES.map((cat) => (
                  <TouchableOpacity
                    key={cat}
                    style={[s.pill, { backgroundColor: selectedCategory === cat ? colors.accent : colors.cardElevated }]}
                    onPress={() => setSelectedCategory(selectedCategory === cat ? null : cat)}
                  >
                    <Text style={[s.pillText, { color: selectedCategory === cat ? "#fff" : colors.textSecondary }]}>{cat.charAt(0).toUpperCase() + cat.slice(1)}</Text>
                  </TouchableOpacity>
                ))}
              </View>
            </ScrollView>
            <TextInput
              style={[s.input, { backgroundColor: colors.inputBg, color: colors.text }]}
              value={expenseInput}
              onChangeText={setExpenseInput}
              placeholder="e.g. $45 at Whole Foods"
              placeholderTextColor={colors.textTertiary}
              multiline autoFocus
            />
            <TouchableOpacity
              style={[s.submitBtn, { backgroundColor: colors.accent }, logging && s.disabled]}
              onPress={handleLogExpense} disabled={logging}
            >
              {logging ? <ActivityIndicator color="#fff" /> : <Text style={s.submitText}>Log Expense</Text>}
            </TouchableOpacity>
            <TouchableOpacity style={s.cancelBtn} onPress={() => setSheetVisible(false)}>
              <Text style={[s.cancelText, { color: colors.textSecondary }]}>Cancel</Text>
            </TouchableOpacity>
          </View>
        </KeyboardAvoidingView>
      </Modal>

      {/* ── Budget Edit Modal ──────────────────────────────────────────────── */}
      <Modal visible={budgetModalVisible} transparent animationType="slide" onRequestClose={() => setBudgetModalVisible(false)}>
        <KeyboardAvoidingView behavior={Platform.OS === "ios" ? "padding" : undefined} style={s.overlay}>
          <View style={[s.sheet, { backgroundColor: colors.card }]}>
            <Text style={[s.sheetTitle, { color: colors.text }]}>
              {editingCategory ? `Budget — ${editingCategory}` : "Add Budget"}
            </Text>
            {!editingCategory && (
              <>
                <Text style={[s.pickerLabel, { color: colors.textSecondary }]}>Category</Text>
                <TextInput
                  style={[s.input, { backgroundColor: colors.inputBg, color: colors.text, minHeight: 0, marginBottom: 12 }]}
                  value={newCategoryInput}
                  onChangeText={setNewCategoryInput}
                  placeholder="e.g. dining"
                  placeholderTextColor={colors.textTertiary}
                  autoFocus
                />
              </>
            )}
            {editingCategory && editingSpend != null && editingSpend > 0 && (
              <Text style={[s.pickerLabel, { color: colors.textSecondary, marginBottom: 12, textTransform: "none", letterSpacing: 0 }]}>
                Spent this month: {fmt(editingSpend)}
              </Text>
            )}
            <Text style={[s.pickerLabel, { color: colors.textSecondary }]}>Type</Text>
            <ScrollView horizontal showsHorizontalScrollIndicator={false} style={{ marginBottom: 12 }}>
              <View style={s.pillRow}>
                {(["discretionary", "fixed", "recurring", "envelope"] as Budget["budget_type"][]).map((t) => (
                  <TouchableOpacity
                    key={t}
                    style={[s.pill, { backgroundColor: editingBudgetType === t ? colors.accent : colors.cardElevated }]}
                    onPress={() => {
                      setEditingBudgetType(t);
                      setEditingPeriod(t === "envelope" ? "biannual" : "monthly");
                    }}
                  >
                    <Text style={[s.pillText, { color: editingBudgetType === t ? "#fff" : colors.textSecondary }]}>{t}</Text>
                  </TouchableOpacity>
                ))}
              </View>
            </ScrollView>
            {editingBudgetType === "envelope" && (
              <>
                <Text style={[s.pickerLabel, { color: colors.textSecondary }]}>Period</Text>
                <ScrollView horizontal showsHorizontalScrollIndicator={false} style={{ marginBottom: 12 }}>
                  <View style={s.pillRow}>
                    {(["monthly", "biannual", "annual"] as Budget["period"][]).map((p) => (
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
            <Text style={[s.pickerLabel, { color: colors.textSecondary }]}>
              {editingBudgetType === "envelope" ? "Pool amount ($)" : "Monthly limit ($)"}
            </Text>
            <TextInput
              style={[s.input, { backgroundColor: colors.inputBg, color: colors.text, minHeight: 0 }]}
              value={budgetInput}
              onChangeText={setBudgetInput}
              placeholder="e.g. 500"
              placeholderTextColor={colors.textTertiary}
              keyboardType="decimal-pad"
              autoFocus={!!editingCategory}
            />
            <TouchableOpacity
              style={[s.submitBtn, { backgroundColor: colors.accent }, savingBudget && s.disabled]}
              onPress={handleSaveBudget} disabled={savingBudget}
            >
              {savingBudget ? <ActivityIndicator color="#fff" /> : <Text style={s.submitText}>Save Limit</Text>}
            </TouchableOpacity>
            <TouchableOpacity style={s.cancelBtn} onPress={() => setBudgetModalVisible(false)}>
              <Text style={[s.cancelText, { color: colors.textSecondary }]}>Cancel</Text>
            </TouchableOpacity>
          </View>
        </KeyboardAvoidingView>
      </Modal>

      {/* ── Update Balances Modal ─────────────────────────────────────────── */}
      <Modal visible={balanceModalVisible} transparent animationType="slide" onRequestClose={() => setBalanceModalVisible(false)}>
        <KeyboardAvoidingView behavior={Platform.OS === "ios" ? "padding" : "height"} style={s.overlay}>
          <ScrollView style={[s.sheet, s.sheetScroll, { backgroundColor: colors.card }]}
            keyboardShouldPersistTaps="handled">
            <Text style={[s.sheetTitle, { color: colors.text }]}>Update Balances</Text>
            <Text style={[s.pickerLabel, { color: colors.textSecondary, marginBottom: 16 }]}>
              Enter today's balances. Credit cards: enter the amount owed (we'll make it negative).
            </Text>
            {[...new Set(accounts.map((a) => a.type))]
              .sort((a, b) => accountTypeOrder(a) - accountTypeOrder(b))
              .map((type) => (
                <View key={type}>
                  <Text style={[s.typeHeader, { color: colors.textTertiary }]}>{type.toUpperCase()}</Text>
                  {accounts
                    .filter((a) => a.type === type)
                    .sort((a, b) => a.name.localeCompare(b.name))
                    .map((acct) => (
                      <View key={acct.id} style={[s.balRow, { borderBottomColor: colors.border }]}>
                        <View style={{ flex: 1 }}>
                          <Text style={[s.balLabel, { color: colors.text }]}>{acct.name}</Text>
                          {lastUpdated[acct.id] && (
                            <Text style={[s.balDate, { color: colors.textTertiary }]}>
                              Updated {new Date(lastUpdated[acct.id] + "T00:00:00").toLocaleDateString("en-US", { month: "short", day: "numeric" })}
                            </Text>
                          )}
                        </View>
                        <TextInput
                          style={[s.balInput, { backgroundColor: colors.inputBg, color: colors.text }]}
                          value={balanceInputs[acct.id] ?? ""}
                          onChangeText={(v) => setBalanceInputs((prev) => ({ ...prev, [acct.id]: v }))}
                          placeholder="0"
                          placeholderTextColor={colors.textTertiary}
                          keyboardType="decimal-pad"
                        />
                      </View>
                    ))}
                </View>
              ))}
            <TouchableOpacity
              style={[s.submitBtn, { backgroundColor: colors.accent, marginTop: 16 }, savingBalances && s.disabled]}
              onPress={handleSaveBalances} disabled={savingBalances}
            >
              {savingBalances ? <ActivityIndicator color="#fff" /> : <Text style={s.submitText}>Save Balances</Text>}
            </TouchableOpacity>
            <TouchableOpacity style={s.cancelBtn} onPress={() => setBalanceModalVisible(false)}>
              <Text style={[s.cancelText, { color: colors.textSecondary }]}>Cancel</Text>
            </TouchableOpacity>
          </ScrollView>
        </KeyboardAvoidingView>
      </Modal>
      {/* ── Add Goal Modal ────────────────────────────────────────────────── */}
      <Modal visible={goalModalVisible} transparent animationType="slide" onRequestClose={() => setGoalModalVisible(false)}>
        <KeyboardAvoidingView behavior={Platform.OS === "ios" ? "padding" : "height"} style={s.overlay}>
          <View style={[s.sheet, { backgroundColor: colors.card }]}>
            <Text style={[s.sheetTitle, { color: colors.text }]}>New Savings Goal</Text>
            <Text style={[s.pickerLabel, { color: colors.textSecondary }]}>Goal name</Text>
            <TextInput
              style={[s.input, { backgroundColor: colors.inputBg, color: colors.text, minHeight: 0, marginBottom: 12 }]}
              value={goalNameInput}
              onChangeText={setGoalNameInput}
              placeholder="e.g. Emergency Fund"
              placeholderTextColor={colors.textTertiary}
              autoFocus
            />
            <Text style={[s.pickerLabel, { color: colors.textSecondary }]}>Target amount ($)</Text>
            <TextInput
              style={[s.input, { backgroundColor: colors.inputBg, color: colors.text, minHeight: 0, marginBottom: 12 }]}
              value={goalAmountInput}
              onChangeText={setGoalAmountInput}
              placeholder="e.g. 10000"
              placeholderTextColor={colors.textTertiary}
              keyboardType="decimal-pad"
            />
            <Text style={[s.pickerLabel, { color: colors.textSecondary }]}>Target date (optional)</Text>
            <TextInput
              style={[s.input, { backgroundColor: colors.inputBg, color: colors.text, minHeight: 0, marginBottom: 16 }]}
              value={goalDateInput}
              onChangeText={setGoalDateInput}
              placeholder="YYYY-MM-DD"
              placeholderTextColor={colors.textTertiary}
            />
            <TouchableOpacity
              style={[s.submitBtn, { backgroundColor: colors.accent }, savingGoal && s.disabled]}
              onPress={handleSaveGoal}
              disabled={savingGoal}
            >
              {savingGoal ? <ActivityIndicator color="#fff" /> : <Text style={s.submitText}>Save Goal</Text>}
            </TouchableOpacity>
            <TouchableOpacity style={s.cancelBtn} onPress={() => setGoalModalVisible(false)}>
              <Text style={[s.cancelText, { color: colors.textSecondary }]}>Cancel</Text>
            </TouchableOpacity>
          </View>
        </KeyboardAvoidingView>
      </Modal>

      {/* ── Add Account Modal ─────────────────────────────────────────────── */}
      <Modal visible={accountModalVisible} transparent animationType="slide" onRequestClose={() => setAccountModalVisible(false)}>
        <KeyboardAvoidingView behavior={Platform.OS === "ios" ? "padding" : "height"} style={s.overlay}>
          <View style={[s.sheet, { backgroundColor: colors.card }]}>
            <Text style={[s.sheetTitle, { color: colors.text }]}>Add Account</Text>
            <Text style={[s.pickerLabel, { color: colors.textSecondary }]}>Account name</Text>
            <TextInput
              style={[s.input, { backgroundColor: colors.inputBg, color: colors.text, minHeight: 0, marginBottom: 12 }]}
              value={accountNameInput}
              onChangeText={setAccountNameInput}
              placeholder="e.g. Fidelity Brokerage"
              placeholderTextColor={colors.textTertiary}
              autoFocus
            />
            <Text style={[s.pickerLabel, { color: colors.textSecondary }]}>Account type</Text>
            <ScrollView horizontal showsHorizontalScrollIndicator={false} style={{ marginBottom: 16 }}>
              <View style={s.pillRow}>
                {(["checking", "savings", "credit", "brokerage", "investment", "crypto"] as Account["type"][]).map((t) => (
                  <TouchableOpacity
                    key={t}
                    style={[s.pill, { backgroundColor: accountTypeInput === t ? colors.accent : colors.cardElevated }]}
                    onPress={() => setAccountTypeInput(t)}
                  >
                    <Text style={[s.pillText, { color: accountTypeInput === t ? "#fff" : colors.textSecondary }]}>{t}</Text>
                  </TouchableOpacity>
                ))}
              </View>
            </ScrollView>
            <TouchableOpacity
              style={[s.submitBtn, { backgroundColor: colors.accent }, savingAccount && s.disabled]}
              onPress={handleSaveAccount}
              disabled={savingAccount}
            >
              {savingAccount ? <ActivityIndicator color="#fff" /> : <Text style={s.submitText}>Add Account</Text>}
            </TouchableOpacity>
            <TouchableOpacity style={s.cancelBtn} onPress={() => setAccountModalVisible(false)}>
              <Text style={[s.cancelText, { color: colors.textSecondary }]}>Cancel</Text>
            </TouchableOpacity>
          </View>
        </KeyboardAvoidingView>
      </Modal>

      <SmartInputSheet
        visible={smartOpen}
        onClose={() => setSmartOpen(false)}
        onConfirmed={() => { setSmartOpen(false); loadData(); }}
        domainLock="finance"
      />
    </SafeAreaView>
  );
}

const s = StyleSheet.create({
  center: { flex: 1, alignItems: "center", justifyContent: "center" },
  content: { padding: 16, paddingBottom: 100 },
  // Hero
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
  heroMilestoneRow: { flexDirection: "row", alignItems: "baseline", gap: 4, marginTop: 2 },
  heroMilestoneValue: { fontSize: 20, fontWeight: "700" },
  heroMilestoneSep: { fontSize: 16 },
  heroMilestoneTarget: { fontSize: 16, fontWeight: "500" },
  heroMilestoneDelta: { fontSize: 12, marginTop: 2 },
  // Account rows
  typeHeader: { fontSize: 11, fontWeight: "600", letterSpacing: 0.8, marginTop: 10, marginBottom: 4 },
  acctRow: { flexDirection: "row", justifyContent: "space-between", alignItems: "center", paddingVertical: 9, borderBottomWidth: StyleSheet.hairlineWidth },
  acctName: { fontSize: 14, flex: 1 },
  acctBalance: { fontSize: 14, fontWeight: "500" },
  // Category rows
  catRow: { flexDirection: "row", justifyContent: "space-between", alignItems: "center", paddingVertical: 10, borderBottomWidth: StyleSheet.hairlineWidth },
  catRight: { flexDirection: "row", alignItems: "center", gap: 8 },
  catName: { fontSize: 14, flex: 1 },
  catAmount: { fontSize: 14, fontWeight: "500" },
  overTag: { borderRadius: 4, paddingHorizontal: 5, paddingVertical: 2 },
  overTagText: { fontSize: 10, fontWeight: "700" },
  // Update button
  updateBtn: { borderRadius: 10, borderWidth: 1, paddingVertical: 10, alignItems: "center", marginTop: 12 },
  updateBtnText: { fontSize: 14, fontWeight: "600" },
  // Pills
  pillRow: { flexDirection: "row", gap: 8 },
  pill: { borderRadius: 20, paddingHorizontal: 14, paddingVertical: 8 },
  pillText: { fontSize: 14, fontWeight: "500" },
  // FAB row
  fabRow: { flexDirection: "row", gap: 10, paddingHorizontal: 16, paddingVertical: 12, borderTopWidth: StyleSheet.hairlineWidth },
  fab: { flex: 1, borderRadius: 12, paddingVertical: 14, alignItems: "center" },
  fabText: { fontSize: 15, fontWeight: "600" },
  // Primary button (inside lists)
  primaryButton: { borderRadius: 12, paddingVertical: 13, alignItems: "center" },
  primaryButtonText: { color: "#fff", fontSize: 15, fontWeight: "600" },
  // Modals
  overlay: { flex: 1, backgroundColor: "#00000088", justifyContent: "flex-end" },
  sheet: { borderTopLeftRadius: 20, borderTopRightRadius: 20, padding: 24, paddingBottom: 40 },
  sheetScroll: { maxHeight: "85%", paddingBottom: 0 },
  sheetTitle: { fontSize: 17, fontWeight: "600", marginBottom: 16 },
  pickerLabel: { fontSize: 12, fontWeight: "500", textTransform: "uppercase", letterSpacing: 0.5 },
  input: { borderRadius: 10, padding: 14, fontSize: 15, minHeight: 80, textAlignVertical: "top", marginBottom: 16 },
  submitBtn: { borderRadius: 12, paddingVertical: 14, alignItems: "center", marginBottom: 10 },
  disabled: { opacity: 0.6 },
  submitText: { color: "#fff", fontSize: 16, fontWeight: "600" },
  cancelBtn: { alignItems: "center", paddingVertical: 10 },
  cancelText: { fontSize: 15 },
  emptyHint: { fontSize: 13, paddingVertical: 8 },
  // Balance modal rows
  balRow: { flexDirection: "row", alignItems: "center", paddingVertical: 8, borderBottomWidth: StyleSheet.hairlineWidth, gap: 12 },
  balLabel: { fontSize: 14 },
  balDate: { fontSize: 11, marginTop: 2 },
  balInput: { width: 120, borderRadius: 8, padding: 10, fontSize: 14, textAlign: "right" },
});
