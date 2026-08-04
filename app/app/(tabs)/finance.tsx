import React, { useState, useEffect, useCallback } from "react";
import {
  View,
  Text,
  ScrollView,
  TouchableOpacity,
  Modal,
  TextInput,
  ActivityIndicator,
  RefreshControl,
  StyleSheet,
  SafeAreaView,
  KeyboardAvoidingView,
  Platform,
} from "react-native";
import { ProgressBar } from "../../components/ProgressBar";
import { TransactionRow } from "../../components/TransactionRow";
import {
  getFinanceSummary,
  getTransactions,
  logExpense,
  getNetWorth,
  getSavingsGoals,
  type CategoryBudget,
  type Transaction,
  type NetWorth,
  type SavingsGoal,
} from "../../lib/api";

export default function FinanceScreen() {
  const now = new Date();
  const [summary, setSummary] = useState<{
    total_spent: number;
    total_budget: number | null;
    categories: CategoryBudget[];
  } | null>(null);
  const [transactions, setTransactions] = useState<Transaction[]>([]);
  const [netWorth, setNetWorth] = useState<NetWorth | null>(null);
  const [goals, setGoals] = useState<SavingsGoal[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [sheetVisible, setSheetVisible] = useState(false);
  const [expenseInput, setExpenseInput] = useState("");
  const [logging, setLogging] = useState(false);

  const loadData = useCallback(async () => {
    try {
      const [sumData, txData, nwData, goalsData] = await Promise.all([
        getFinanceSummary(now.getFullYear(), now.getMonth() + 1),
        getTransactions(),
        getNetWorth(),
        getSavingsGoals(),
      ]);
      setSummary(sumData);
      setTransactions(txData.transactions.slice(0, 10));
      setNetWorth(nwData);
      setGoals(goalsData.goals);
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
      const tx = await logExpense(expenseInput.trim());
      setTransactions((prev) => [tx, ...prev]);
      setExpenseInput("");
      setSheetVisible(false);
      loadData(); // refresh summary
    } finally {
      setLogging(false);
    }
  };

  const formatCurrency = (n: number) =>
    new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(n);

  const monthName = now.toLocaleDateString("en-US", { month: "long" });

  if (loading) {
    return (
      <SafeAreaView style={styles.safe}>
        <View style={styles.center}><ActivityIndicator color="#007AFF" /></View>
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={styles.safe}>
      <ScrollView
        style={styles.scroll}
        contentContainerStyle={styles.content}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={handleRefresh} />}
      >
        {/* Month spend vs budget */}
        {summary && (
          <View style={styles.card}>
            <Text style={styles.sectionTitle}>{monthName} Spending</Text>
            {summary.total_budget != null ? (
              <ProgressBar
                label="Total"
                value={summary.total_spent}
                target={summary.total_budget}
                unit=""
                color="#30D158"
              />
            ) : (
              <Text style={styles.bigNumber}>{formatCurrency(summary.total_spent)}</Text>
            )}
          </View>
        )}

        {/* Log Expense CTA */}
        <TouchableOpacity
          style={styles.primaryButton}
          onPress={() => setSheetVisible(true)}
        >
          <Text style={styles.primaryButtonText}>+ Log Expense</Text>
        </TouchableOpacity>

        {/* Category breakdown */}
        {summary && summary.categories.length > 0 && (
          <View style={styles.card}>
            <Text style={styles.sectionTitle}>By Category</Text>
            {summary.categories.map((cat) => (
              <View key={cat.category} style={styles.categoryRow}>
                <Text style={styles.categoryName}>{cat.category}</Text>
                <Text style={[styles.categoryAmount, cat.over_budget && styles.overBudget]}>
                  {formatCurrency(cat.spent)}
                  {cat.budget != null && (
                    <Text style={styles.categoryBudget}> / {formatCurrency(cat.budget)}</Text>
                  )}
                  {cat.over_budget && <Text style={styles.overTag}> OVER</Text>}
                </Text>
              </View>
            ))}
          </View>
        )}

        {/* Net worth snapshot */}
        {netWorth && (
          <View style={styles.card}>
            <Text style={styles.sectionTitle}>Net Worth</Text>
            <Text style={styles.bigNumber}>{formatCurrency(netWorth.total)}</Text>
            <Text style={styles.netWorthNote}>
              As of {new Date(netWorth.snapshot_date).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" })}
              {" · "}Manual snapshots only
            </Text>
          </View>
        )}

        {/* Savings goals */}
        {goals.length > 0 && (
          <View style={styles.card}>
            <Text style={styles.sectionTitle}>Savings Goals</Text>
            {goals.map((goal) => (
              <View key={goal.id} style={styles.goalRow}>
                <ProgressBar
                  label={goal.name}
                  value={goal.current_amount}
                  target={goal.target_amount}
                  unit=""
                  color="#30D158"
                />
              </View>
            ))}
          </View>
        )}

        {/* Recent transactions */}
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Recent Transactions</Text>
          {transactions.length === 0 && (
            <Text style={styles.emptyText}>No transactions yet.</Text>
          )}
          {transactions.map((tx) => (
            <TransactionRow key={tx.id} transaction={tx} />
          ))}
        </View>
      </ScrollView>

      {/* Log Expense Sheet */}
      <Modal
        visible={sheetVisible}
        transparent
        animationType="slide"
        onRequestClose={() => setSheetVisible(false)}
      >
        <KeyboardAvoidingView
          behavior={Platform.OS === "ios" ? "padding" : undefined}
          style={styles.modalOverlay}
        >
          <View style={styles.modalSheet}>
            <Text style={styles.modalTitle}>Log an Expense</Text>
            <TextInput
              style={styles.textInput}
              value={expenseInput}
              onChangeText={setExpenseInput}
              placeholder="e.g. $45 at Whole Foods, groceries"
              placeholderTextColor="#636366"
              multiline
              autoFocus
            />
            <TouchableOpacity
              style={[styles.submitButton, logging && styles.buttonDisabled]}
              onPress={handleLogExpense}
              disabled={logging}
            >
              {logging ? <ActivityIndicator color="#fff" /> : <Text style={styles.submitText}>Log Expense</Text>}
            </TouchableOpacity>
            <TouchableOpacity style={styles.cancelButton} onPress={() => setSheetVisible(false)}>
              <Text style={styles.cancelText}>Cancel</Text>
            </TouchableOpacity>
          </View>
        </KeyboardAvoidingView>
      </Modal>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: "#000" },
  scroll: { flex: 1 },
  content: { padding: 16, paddingBottom: 40 },
  center: { flex: 1, alignItems: "center", justifyContent: "center" },
  card: { backgroundColor: "#1C1C1E", borderRadius: 12, padding: 16, marginBottom: 16 },
  section: { marginBottom: 20 },
  sectionTitle: { color: "#fff", fontSize: 15, fontWeight: "600", marginBottom: 12 },
  bigNumber: { color: "#fff", fontSize: 28, fontWeight: "700", marginBottom: 4 },
  netWorthNote: { color: "#8E8E93", fontSize: 12 },
  primaryButton: {
    backgroundColor: "#007AFF",
    borderRadius: 12,
    paddingVertical: 14,
    alignItems: "center",
    marginBottom: 16,
  },
  primaryButtonText: { color: "#fff", fontSize: 16, fontWeight: "600" },
  categoryRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    paddingVertical: 8,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: "#2C2C2E",
  },
  categoryName: { color: "#EBEBF5CC", fontSize: 14, flex: 1 },
  categoryAmount: { color: "#fff", fontSize: 14, fontWeight: "500" },
  overBudget: { color: "#FF453A" },
  categoryBudget: { color: "#8E8E93", fontWeight: "400" },
  overTag: { color: "#FF453A", fontSize: 11, fontWeight: "700" },
  goalRow: { marginBottom: 4 },
  emptyText: { color: "#8E8E93", fontSize: 14 },
  modalOverlay: { flex: 1, backgroundColor: "#00000088", justifyContent: "flex-end" },
  modalSheet: {
    backgroundColor: "#1C1C1E",
    borderTopLeftRadius: 20,
    borderTopRightRadius: 20,
    padding: 24,
    paddingBottom: 40,
  },
  modalTitle: { color: "#fff", fontSize: 17, fontWeight: "600", marginBottom: 16 },
  textInput: {
    backgroundColor: "#2C2C2E",
    borderRadius: 10,
    padding: 14,
    color: "#fff",
    fontSize: 15,
    minHeight: 80,
    textAlignVertical: "top",
    marginBottom: 16,
  },
  submitButton: {
    backgroundColor: "#007AFF",
    borderRadius: 12,
    paddingVertical: 14,
    alignItems: "center",
    marginBottom: 10,
  },
  buttonDisabled: { opacity: 0.6 },
  submitText: { color: "#fff", fontSize: 16, fontWeight: "600" },
  cancelButton: { alignItems: "center", paddingVertical: 10 },
  cancelText: { color: "#8E8E93", fontSize: 15 },
});
