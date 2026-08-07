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
