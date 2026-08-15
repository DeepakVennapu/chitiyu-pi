import React, { useState } from "react";
import {
  Modal, View, Text, TextInput, TouchableOpacity,
  KeyboardAvoidingView, ActivityIndicator, Platform, StyleSheet, Alert,
} from "react-native";
import { createGoal } from "../../lib/api";
import { useTheme } from "../../lib/theme";

interface Props {
  visible: boolean;
  onClose: () => void;
  onSaved: () => void;
}

export function AddGoalSheet({ visible, onClose, onSaved }: Props) {
  const { colors } = useTheme();
  const [name, setName] = useState("");
  const [amount, setAmount] = useState("");
  const [date, setDate] = useState("");
  const [saving, setSaving] = useState(false);

  const handleClose = () => { setName(""); setAmount(""); setDate(""); onClose(); };

  const handleSave = async () => {
    if (!name.trim()) { Alert.alert("Missing name", "Enter a goal name."); return; }
    const parsed = parseFloat(amount);
    if (isNaN(parsed) || parsed <= 0) { Alert.alert("Invalid amount", "Enter a positive amount."); return; }
    setSaving(true);
    try {
      await createGoal({ name: name.trim(), target_amount: parsed, target_date: date.trim() || null });
      setName(""); setAmount(""); setDate("");
      onSaved();
    } catch (e: any) {
      Alert.alert("Couldn't save goal", e?.message ?? "Please try again.");
    } finally {
      setSaving(false);
    }
  };

  return (
    <Modal visible={visible} transparent animationType="slide" onRequestClose={handleClose}>
      <KeyboardAvoidingView behavior={Platform.OS === "ios" ? "padding" : "height"} style={s.overlay}>
        <View style={[s.sheet, { backgroundColor: colors.card }]}>
          <Text style={[s.title, { color: colors.text }]}>New Savings Goal</Text>
          <Text style={[s.label, { color: colors.textSecondary }]}>Goal name</Text>
          <TextInput
            style={[s.input, { backgroundColor: colors.inputBg, color: colors.text }]}
            value={name} onChangeText={setName}
            placeholder="e.g. Emergency Fund" placeholderTextColor={colors.textTertiary} autoFocus
          />
          <Text style={[s.label, { color: colors.textSecondary }]}>Target amount ($)</Text>
          <TextInput
            style={[s.input, { backgroundColor: colors.inputBg, color: colors.text }]}
            value={amount} onChangeText={setAmount}
            placeholder="e.g. 10000" placeholderTextColor={colors.textTertiary} keyboardType="decimal-pad"
          />
          <Text style={[s.label, { color: colors.textSecondary }]}>Target date (optional)</Text>
          <TextInput
            style={[s.input, { backgroundColor: colors.inputBg, color: colors.text, marginBottom: 16 }]}
            value={date} onChangeText={setDate}
            placeholder="YYYY-MM-DD" placeholderTextColor={colors.textTertiary}
          />
          <TouchableOpacity
            style={[s.submitBtn, { backgroundColor: colors.accent }, saving && s.disabled]}
            onPress={handleSave} disabled={saving}
          >
            {saving ? <ActivityIndicator color="#fff" /> : <Text style={s.submitText}>Save Goal</Text>}
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
  input: { borderRadius: 10, padding: 14, fontSize: 15, minHeight: 0, marginBottom: 12 },
  submitBtn: { borderRadius: 12, paddingVertical: 14, alignItems: "center", marginBottom: 10 },
  disabled: { opacity: 0.6 },
  submitText: { color: "#fff", fontSize: 16, fontWeight: "600" },
  cancelBtn: { alignItems: "center", paddingVertical: 10 },
  cancelText: { fontSize: 15 },
});
