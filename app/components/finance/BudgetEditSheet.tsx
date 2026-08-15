// app/components/finance/BudgetEditSheet.tsx
import React, { useState, useEffect } from "react";
import {
  Modal, View, Text, TextInput, TouchableOpacity, ScrollView,
  KeyboardAvoidingView, ActivityIndicator, Platform, StyleSheet, Alert,
} from "react-native";
import { setBudgetWithType, deleteBudget, type Budget } from "../../lib/api";
import { useTheme } from "../../lib/theme";
import { fmt } from "../../lib/financeUtils";

interface Props {
  visible: boolean;
  editingCategory: string | null;
  editingBudgetId: number | null;
  editingSpend: number | null;
  initialBudgetType: Budget["budget_type"];
  initialPeriod: Budget["period"];
  initialAmount: string;
  onClose: () => void;
  onSaved: () => void;
  onDeleted: () => void;
}

export function BudgetEditSheet({
  visible, editingCategory, editingBudgetId, editingSpend,
  initialBudgetType, initialPeriod, initialAmount,
  onClose, onSaved, onDeleted,
}: Props) {
  const { colors } = useTheme();
  const [budgetType, setBudgetType] = useState<Budget["budget_type"]>(initialBudgetType);
  const [period, setPeriod] = useState<Budget["period"]>(initialPeriod);
  const [amount, setAmount] = useState(initialAmount);
  const [newCategory, setNewCategory] = useState("");
  const [saving, setSaving] = useState(false);

  // Sync initial values when sheet opens
  useEffect(() => {
    if (visible) {
      setBudgetType(initialBudgetType);
      setPeriod(initialPeriod);
      setAmount(initialAmount);
      setNewCategory("");
    }
  }, [visible, initialBudgetType, initialPeriod, initialAmount]);

  const handleSave = async () => {
    const targetCategory = editingCategory || newCategory.trim();
    if (!targetCategory) { Alert.alert("Missing category", "Enter a category name."); return; }
    const parsed = parseFloat(amount);
    if (isNaN(parsed) || parsed <= 0) { Alert.alert("Invalid amount", "Enter a positive number."); return; }
    setSaving(true);
    try {
      await setBudgetWithType(targetCategory, parsed, budgetType, period);
      onSaved();
    } catch (e: any) {
      Alert.alert("Couldn't save budget", e?.message ?? "Please try again.");
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = () => {
    if (editingBudgetId == null || !editingCategory) return;
    Alert.alert("Delete budget?", `Remove budget for "${editingCategory}"?`, [
      { text: "Cancel", style: "cancel" },
      {
        text: "Delete", style: "destructive", onPress: async () => {
          try {
            await deleteBudget(editingBudgetId);
            onDeleted();
          } catch (e: any) {
            Alert.alert("Couldn't delete budget", e?.message ?? "Please try again.");
          }
        },
      },
    ]);
  };

  return (
    <Modal visible={visible} transparent animationType="slide" onRequestClose={onClose}>
      <KeyboardAvoidingView behavior={Platform.OS === "ios" ? "padding" : undefined} style={s.overlay}>
        <View style={[s.sheet, { backgroundColor: colors.card }]}>
          <Text style={[s.title, { color: colors.text }]}>
            {editingCategory ? `Budget — ${editingCategory}` : "Add Budget"}
          </Text>

          {!editingCategory && (
            <>
              <Text style={[s.label, { color: colors.textSecondary }]}>Category</Text>
              <TextInput
                style={[s.input, { backgroundColor: colors.inputBg, color: colors.text, minHeight: 0, marginBottom: 12 }]}
                value={newCategory}
                onChangeText={setNewCategory}
                placeholder="e.g. dining"
                placeholderTextColor={colors.textTertiary}
                autoFocus
              />
            </>
          )}

          {editingCategory && editingSpend != null && editingSpend > 0 && (
            <Text style={[s.label, { color: colors.textSecondary, marginBottom: 12, textTransform: "none", letterSpacing: 0 }]}>
              Spent this month: {fmt(editingSpend)}
            </Text>
          )}

          <Text style={[s.label, { color: colors.textSecondary }]}>Type</Text>
          <ScrollView horizontal showsHorizontalScrollIndicator={false} style={{ marginBottom: 12 }}>
            <View style={s.pillRow}>
              {(["discretionary", "fixed", "recurring", "envelope"] as Budget["budget_type"][]).map((t) => (
                <TouchableOpacity
                  key={t}
                  style={[s.pill, { backgroundColor: budgetType === t ? colors.accent : colors.cardElevated }]}
                  onPress={() => {
                    setBudgetType(t);
                    setPeriod(t === "envelope" ? "biannual" : "monthly");
                  }}
                >
                  <Text style={[s.pillText, { color: budgetType === t ? "#fff" : colors.textSecondary }]}>{t}</Text>
                </TouchableOpacity>
              ))}
            </View>
          </ScrollView>

          {budgetType === "envelope" && (
            <>
              <Text style={[s.label, { color: colors.textSecondary }]}>Period</Text>
              <ScrollView horizontal showsHorizontalScrollIndicator={false} style={{ marginBottom: 12 }}>
                <View style={s.pillRow}>
                  {(["monthly", "biannual", "annual"] as Budget["period"][]).map((p) => (
                    <TouchableOpacity
                      key={p}
                      style={[s.pill, { backgroundColor: period === p ? colors.accent : colors.cardElevated }]}
                      onPress={() => setPeriod(p)}
                    >
                      <Text style={[s.pillText, { color: period === p ? "#fff" : colors.textSecondary }]}>{p}</Text>
                    </TouchableOpacity>
                  ))}
                </View>
              </ScrollView>
            </>
          )}

          <Text style={[s.label, { color: colors.textSecondary }]}>
            {budgetType === "envelope" ? "Pool amount ($)" : "Monthly limit ($)"}
          </Text>
          <TextInput
            style={[s.input, { backgroundColor: colors.inputBg, color: colors.text, minHeight: 0 }]}
            value={amount}
            onChangeText={setAmount}
            placeholder="e.g. 500"
            placeholderTextColor={colors.textTertiary}
            keyboardType="decimal-pad"
            autoFocus={!!editingCategory}
          />

          <TouchableOpacity
            style={[s.submitBtn, { backgroundColor: colors.accent }, saving && s.disabled]}
            onPress={handleSave}
            disabled={saving}
          >
            {saving ? <ActivityIndicator color="#fff" /> : <Text style={s.submitText}>Save Limit</Text>}
          </TouchableOpacity>

          {editingBudgetId != null && (
            <TouchableOpacity style={s.cancelBtn} onPress={handleDelete}>
              <Text style={[s.cancelText, { color: colors.accentRed }]}>Delete Budget</Text>
            </TouchableOpacity>
          )}

          <TouchableOpacity style={s.cancelBtn} onPress={onClose}>
            <Text style={[s.cancelText, { color: colors.textSecondary }]}>Cancel</Text>
          </TouchableOpacity>
        </View>
      </KeyboardAvoidingView>
    </Modal>
  );
}

const s = StyleSheet.create({
  overlay: { flex: 1, backgroundColor: "#00000088", justifyContent: "flex-end" },
  sheet: { borderTopLeftRadius: 20, borderTopRightRadius: 20, padding: 24, paddingBottom: 40 },
  title: { fontSize: 17, fontWeight: "600", marginBottom: 16 },
  label: { fontSize: 12, fontWeight: "500", textTransform: "uppercase", letterSpacing: 0.5 },
  pillRow: { flexDirection: "row", gap: 8 },
  pill: { borderRadius: 20, paddingHorizontal: 14, paddingVertical: 8 },
  pillText: { fontSize: 14, fontWeight: "500" },
  input: { borderRadius: 10, padding: 14, fontSize: 15, minHeight: 80, textAlignVertical: "top", marginBottom: 16 },
  submitBtn: { borderRadius: 12, paddingVertical: 14, alignItems: "center", marginBottom: 10 },
  disabled: { opacity: 0.6 },
  submitText: { color: "#fff", fontSize: 16, fontWeight: "600" },
  cancelBtn: { alignItems: "center", paddingVertical: 10 },
  cancelText: { fontSize: 15 },
});
