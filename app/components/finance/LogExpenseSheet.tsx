import React, { useState } from "react";
import {
  Modal, View, Text, TextInput, TouchableOpacity, ScrollView,
  KeyboardAvoidingView, ActivityIndicator, Platform, StyleSheet, Alert,
} from "react-native";
import { logExpense, type Transaction } from "../../lib/api";
import { useTheme } from "../../lib/theme";

const EXPENSE_CATEGORIES = ["groceries", "dining", "fuel", "shopping", "misc", "home", "travel", "insurance", "gifts", "other"];

interface Props {
  visible: boolean;
  onClose: () => void;
  onLogged: (tx: Transaction) => void;
}

export function LogExpenseSheet({ visible, onClose, onLogged }: Props) {
  const { colors } = useTheme();
  const [expenseInput, setExpenseInput] = useState("");
  const [selectedCategory, setSelectedCategory] = useState<string | null>(null);
  const [logging, setLogging] = useState(false);

  const handleClose = () => {
    setExpenseInput("");
    setSelectedCategory(null);
    onClose();
  };

  const handleLog = async () => {
    if (!expenseInput.trim()) return;
    setLogging(true);
    try {
      const tx = await logExpense(expenseInput.trim(), selectedCategory ?? undefined);
      setExpenseInput("");
      setSelectedCategory(null);
      onLogged(tx);
    } catch (e: any) {
      Alert.alert("Couldn't log expense", e?.message ?? "Please try again.");
    } finally {
      setLogging(false);
    }
  };

  return (
    <Modal visible={visible} transparent animationType="slide" onRequestClose={handleClose}>
      <KeyboardAvoidingView behavior={Platform.OS === "ios" ? "padding" : undefined} style={s.overlay}>
        <View style={[s.sheet, { backgroundColor: colors.card }]}>
          <Text style={[s.title, { color: colors.text }]}>Log an Expense</Text>
          <Text style={[s.label, { color: colors.textSecondary }]}>Category (optional)</Text>
          <ScrollView horizontal showsHorizontalScrollIndicator={false} style={{ marginBottom: 16 }}>
            <View style={s.pillRow}>
              {EXPENSE_CATEGORIES.map((cat) => (
                <TouchableOpacity
                  key={cat}
                  style={[s.pill, { backgroundColor: selectedCategory === cat ? colors.accent : colors.cardElevated }]}
                  onPress={() => setSelectedCategory(selectedCategory === cat ? null : cat)}
                >
                  <Text style={[s.pillText, { color: selectedCategory === cat ? "#fff" : colors.textSecondary }]}>
                    {cat.charAt(0).toUpperCase() + cat.slice(1)}
                  </Text>
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
            multiline
            autoFocus
          />
          <TouchableOpacity
            style={[s.submitBtn, { backgroundColor: colors.accent }, logging && s.disabled]}
            onPress={handleLog}
            disabled={logging}
          >
            {logging ? <ActivityIndicator color="#fff" /> : <Text style={s.submitText}>Log Expense</Text>}
          </TouchableOpacity>
          <TouchableOpacity style={s.cancelBtn} onPress={handleClose}>
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
