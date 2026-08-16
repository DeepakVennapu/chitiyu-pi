import React, { useState, useEffect, useCallback } from "react";
import { SmartInputSheet } from "../../components/SmartInputSheet";
import { LogExpenseSheet } from "../../components/finance/LogExpenseSheet";
import { BudgetEditSheet } from "../../components/finance/BudgetEditSheet";
import { UpdateBalancesSheet } from "../../components/finance/UpdateBalancesSheet";
import { AddGoalSheet } from "../../components/finance/AddGoalSheet";
import { AddAccountSheet } from "../../components/finance/AddAccountSheet";
import {
  View, Text, ScrollView, TouchableOpacity,
  ActivityIndicator, RefreshControl, StyleSheet, SafeAreaView, Alert,
} from "react-native";
import { Accordion } from "../../components/Accordion";
import { ProgressBar } from "../../components/ProgressBar";
import { TransactionRow } from "../../components/TransactionRow";
import { MilestoneRow } from "../../components/finance/MilestoneRow";
import {
  getFinanceSummary, getTransactions, getSavingsGoals,
  deleteTransaction, setBudgetWithType, deleteBudget, getBudgets, getAccounts,
  getLatestBalances, getMilestones, patchMilestoneActual,
  type CategoryBudget, type Budget, type Transaction, type SavingsGoal,
  type Account, type AccountBalance, type FinancialMilestone,
} from "../../lib/api";
import { useTheme } from "../../lib/theme";
import { fmt, fmtFull, accountTypeOrder } from "../../lib/financeUtils";

// ── main screen ───────────────────────────────────────────────────────────────

export default function FinanceScreen() {
  const { colors } = useTheme();
  const now = new Date();
  const [summaryYear, setSummaryYear] = useState(now.getFullYear());
  const [summaryMonth, setSummaryMonth] = useState(now.getMonth() + 1);
  const isCurrentMonth = summaryYear === now.getFullYear() && summaryMonth === now.getMonth() + 1;
  const monthName = new Date(summaryYear, summaryMonth - 1, 1).toLocaleDateString("en-US", { month: "long", year: "numeric" });

  const [summary, setSummary] = useState<import("../../lib/api").FinanceSummary | null>(null);
  const [budgetList, setBudgetList] = useState<Budget[]>([]);
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

  // Log expense sheet
  const [logExpenseVisible, setLogExpenseVisible] = useState(false);

  // Budget edit sheet
  const [budgetSheetVisible, setBudgetSheetVisible] = useState(false);
  const [budgetEditConfig, setBudgetEditConfig] = useState<{
    category: string | null;
    budgetId: number | null;
    spend: number | null;
    budgetType: Budget["budget_type"];
    period: Budget["period"];
    amount: string;
  }>({ category: null, budgetId: null, spend: null, budgetType: "discretionary", period: "monthly", amount: "" });

  // Balance update sheet
  const [balanceSheetVisible, setBalanceSheetVisible] = useState(false);

  // Add Goal sheet
  const [goalSheetVisible, setGoalSheetVisible] = useState(false);

  // Add Account sheet
  const [accountSheetVisible, setAccountSheetVisible] = useState(false);

  const loadData = useCallback(async () => {
    setError(null);
    try {
      const [sumData, txData, goalsData, accountsData, balancesData, milestonesData, budgetsData] =
        await Promise.all([
          getFinanceSummary(summaryYear, summaryMonth),
          getTransactions(),
          getSavingsGoals(),
          getAccounts(),
          getLatestBalances(),
          getMilestones(),
          getBudgets(),
        ]);
      setSummary(sumData);
      setTransactions(txData.transactions.slice(0, 20));
      setGoals(goalsData.goals);
      setAccounts(accountsData.accounts);
      setBalances(balancesData.balances);
      setComputedNetWorth(balancesData.computed_net_worth);
      setMilestonePeriods(milestonesData.periods);
      setMilestones(milestonesData.milestones);
      setBudgetList(budgetsData);
    } catch (e: any) {
      setError(e?.message ?? "Failed to load finance data");
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [summaryYear, summaryMonth]);

  useEffect(() => { loadData(); }, [loadData]);

  useEffect(() => {
    if (milestonePeriods.length > 0 && selectedPeriod === null) {
      setSelectedPeriod(milestonePeriods[0]);
    }
  }, [milestonePeriods]);

  const handleRefresh = () => { setRefreshing(true); loadData(); };

  const shiftMonth = (delta: number) => {
    let m = summaryMonth + delta;
    let y = summaryYear;
    if (m > 12) { m = 1; y += 1; }
    if (m < 1) { m = 12; y -= 1; }
    setSummaryMonth(m);
    setSummaryYear(y);
  };

  const handleConfirmMilestone = (m: FinancialMilestone) => {
    const defaultVal = m.current_balance != null ? String(Math.round(m.current_balance)) : "";
    Alert.prompt(
      "Confirm Chase balance",
      `Enter actual Chase Checking balance for ${m.target_date}:`,
      async (val) => {
        const amount = parseFloat(val ?? "");
        if (isNaN(amount)) return;
        try {
          await patchMilestoneActual(m.target_date, amount);
          await loadData();
        } catch (e: any) {
          Alert.alert("Couldn't save", e?.message ?? "Please try again.");
        }
      },
      "plain-text",
      defaultVal,
      "decimal-pad"
    );
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
    const budgetRow = budgetList.find(
      (b) => b.category.toLowerCase() === category.toLowerCase()
    );
    setBudgetEditConfig({
      category: category || null,
      budgetId: budgetRow?.id ?? null,
      spend: catData?.spent ?? null,
      budgetType: catData?.budget_type ?? "discretionary",
      period: catData?.period ?? "monthly",
      amount: catData?.budget != null ? String(catData.budget) : "",
    });
    setBudgetSheetVisible(true);
  };




  // ── derived ──────────────────────────────────────────────────────────────────

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
            {/* Month navigator */}
            <View style={s.monthNav}>
              <TouchableOpacity onPress={() => shiftMonth(-1)} style={s.monthArrow}>
                <Text style={[s.monthArrowText, { color: colors.accent }]}>‹</Text>
              </TouchableOpacity>
              <Text style={[s.monthNavLabel, { color: colors.textSecondary }]}>
                {monthName.toUpperCase()}
              </Text>
              <TouchableOpacity
                onPress={() => shiftMonth(1)}
                style={s.monthArrow}
                disabled={isCurrentMonth}
              >
                <Text style={[s.monthArrowText, { color: isCurrentMonth ? colors.textTertiary : colors.accent }]}>›</Text>
              </TouchableOpacity>
            </View>
            {/* Part 1: Discretionary spend */}
            <Text style={[s.heroLabel, { color: colors.textSecondary }]}>
              DISCRETIONARY
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

        {/* ── SAVINGS TIMELINE ────────────────────────────────────────────── */}
        {milestones.length > 0 && (
          <Accordion title="Savings Timeline" defaultOpen>
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
              <MilestoneRow key={m.id} m={m} onConfirm={handleConfirmMilestone} />
            ))}
          </Accordion>
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
            onPress={() => setAccountSheetVisible(true)}
          >
            <Text style={[s.updateBtnText, { color: colors.textTertiary }]}>+ Add Account</Text>
          </TouchableOpacity>
        </Accordion>

        {/* ── DISCRETIONARY ────────────────────────────────────────────── */}
        <Accordion
          title="Discretionary"
          badge={summary ? `${fmt(summary.discretionary_spent)} / ${fmt(summary.discretionary_budget)}` : undefined}
          defaultOpen
        >
          {summary && summary.by_type.discretionary.length === 0 && (
            <Text style={[s.emptyHint, { color: colors.textSecondary }]}>No discretionary budgets set.</Text>
          )}
          {summary && summary.by_type.discretionary.map((cat) => {
            const budgetId = summary.categories.find(c => c.category === cat.category) as any;
            return (
              <View key={cat.category} style={[s.catRow, { borderBottomColor: colors.border }]}>
                <TouchableOpacity style={{ flex: 1 }} onPress={() => openBudgetEdit(cat.category)}>
                  <Text style={[s.catName, { color: colors.text }]}>
                    {cat.category.charAt(0).toUpperCase() + cat.category.slice(1)}
                  </Text>
                </TouchableOpacity>
                <View style={s.catRight}>
                  <TouchableOpacity onPress={() => openBudgetEdit(cat.category)}>
                    <Text style={[s.catAmount, { color: cat.over_budget ? colors.accentRed : colors.text }]}>
                      {fmt(cat.spent)}
                      {cat.budget != null && (
                        <Text style={{ color: colors.textSecondary, fontWeight: "400" }}>
                          {" "}/ {fmt(cat.budget)}
                        </Text>
                      )}
                    </Text>
                  </TouchableOpacity>
                  {cat.over_budget && (
                    <View style={[s.overTag, { backgroundColor: colors.accentRed + "22" }]}>
                      <Text style={[s.overTagText, { color: colors.accentRed }]}>OVER</Text>
                    </View>
                  )}
                  <Text style={{ color: colors.textTertiary, fontSize: 12 }}>›</Text>
                </View>
              </View>
            );
          })}
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
              ? fmt(summary.by_type.fixed.reduce((sum, c) => sum + (c.budget ?? 0), 0)) + "/mo"
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
            onPress={() => setGoalSheetVisible(true)}
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
          style={[s.fab, { backgroundColor: colors.accentGreen + "22", borderWidth: 1, borderColor: colors.accentGreen }]}
          onPress={() => setSmartOpen(true)}
        >
          <Text style={[s.fabText, { color: colors.accentGreen }]}>+ Log Expense</Text>
        </TouchableOpacity>
        {accounts.length > 0 && (
          <TouchableOpacity
            style={[s.fab, { backgroundColor: colors.accent }]}
            onPress={() => setBalanceSheetVisible(true)}
          >
            <Text style={[s.fabText, { color: "#fff" }]}>Update Balances</Text>
          </TouchableOpacity>
        )}
      </View>

      {/* ── Log Expense Sheet ─────────────────────────────────────────────── */}
      <LogExpenseSheet
        visible={logExpenseVisible}
        onClose={() => setLogExpenseVisible(false)}
        onLogged={(tx) => { setTransactions((prev) => [tx, ...prev]); loadData(); }}
      />


      {/* ── Budget Edit Sheet ──────────────────────────────────────────────── */}
      <BudgetEditSheet
        visible={budgetSheetVisible}
        editingCategory={budgetEditConfig.category}
        editingBudgetId={budgetEditConfig.budgetId}
        editingSpend={budgetEditConfig.spend}
        initialBudgetType={budgetEditConfig.budgetType}
        initialPeriod={budgetEditConfig.period}
        initialAmount={budgetEditConfig.amount}
        onClose={() => setBudgetSheetVisible(false)}
        onSaved={() => { setBudgetSheetVisible(false); loadData(); }}
        onDeleted={() => { setBudgetSheetVisible(false); loadData(); }}
      />

      {/* ── Update Balances Sheet ──────────────────────────────────────────── */}
      <UpdateBalancesSheet
        visible={balanceSheetVisible}
        accounts={accounts}
        balances={balances}
        onClose={() => setBalanceSheetVisible(false)}
        onSaved={(nw) => { setComputedNetWorth(nw); setBalanceSheetVisible(false); loadData(); }}
      />
      {/* ── Add Goal Sheet ────────────────────────────────────────────────── */}
      <AddGoalSheet
        visible={goalSheetVisible}
        onClose={() => setGoalSheetVisible(false)}
        onSaved={() => { setGoalSheetVisible(false); loadData(); }}
      />

      {/* ── Add Account Sheet ─────────────────────────────────────────────── */}
      <AddAccountSheet
        visible={accountSheetVisible}
        onClose={() => setAccountSheetVisible(false)}
        onSaved={() => { setAccountSheetVisible(false); loadData(); }}
      />

      <LogExpenseSheet
        visible={logExpenseVisible}
        onClose={() => setLogExpenseVisible(false)}
        onLogged={(tx) => { setTransactions((prev) => [tx, ...prev]); loadData(); }}
      />

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
  // Month nav
  monthNav: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", marginBottom: 16 },
  monthArrow: { padding: 4 },
  monthArrowText: { fontSize: 22, fontWeight: "600" },
  monthNavLabel: { fontSize: 12, fontWeight: "600", letterSpacing: 0.8 },
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
  // FAB row — paddingRight leaves room for the global FAB (56px + 20px margin + 10px gap)
  fabRow: { flexDirection: "row", gap: 10, paddingHorizontal: 16, paddingVertical: 12, paddingRight: 92, borderTopWidth: StyleSheet.hairlineWidth },
  fab: { flex: 1, borderRadius: 12, paddingVertical: 14, alignItems: "center" },
  fabText: { fontSize: 15, fontWeight: "600" },
  // Primary button (inside lists)
  primaryButton: { borderRadius: 12, paddingVertical: 13, alignItems: "center" },
  primaryButtonText: { color: "#fff", fontSize: 15, fontWeight: "600" },
  emptyHint: { fontSize: 13, paddingVertical: 8 },
});
