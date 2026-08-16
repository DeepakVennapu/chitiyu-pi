import React, { useState } from "react";
import {
  Modal, View, Text, TextInput, TouchableOpacity, ScrollView,
  KeyboardAvoidingView, ActivityIndicator, Platform, StyleSheet, Alert,
} from "react-native";
import { createAccount, type Account } from "../../lib/api";
import { useTheme } from "../../lib/theme";

interface Props {
  visible: boolean;
  onClose: () => void;
  onSaved: () => void;
}

const ACCOUNT_TYPES: Account["type"][] = ["checking", "savings", "credit", "brokerage", "investment", "crypto"];

export function AddAccountSheet({ visible, onClose, onSaved }: Props) {
  const { colors } = useTheme();
  const [name, setName] = useState("");
  const [accountType, setAccountType] = useState<Account["type"]>("checking");
  const [saving, setSaving] = useState(false);

  const handleClose = () => { setName(""); setAccountType("checking"); onClose(); };

  const handleSave = async () => {
    if (!name.trim()) { Alert.alert("Missing name", "Enter an account name."); return; }
    setSaving(true);
    try {
      await createAccount(name.trim(), accountType);
      setName(""); setAccountType("checking");
      onSaved();
    } catch (e: any) {
      Alert.alert("Couldn't add account", e?.message ?? "Please try again.");
    } finally {
      setSaving(false);
    }
  };

  return (
    <Modal visible={visible} transparent animationType="slide" onRequestClose={handleClose}>
      <KeyboardAvoidingView behavior={Platform.OS === "ios" ? "padding" : "height"} style={s.overlay}>
        <View style={[s.sheet, { backgroundColor: colors.card }]}>
          <Text style={[s.title, { color: colors.text }]}>Add Account</Text>
          <Text style={[s.label, { color: colors.textSecondary }]}>Account name</Text>
          <TextInput
            style={[s.input, { backgroundColor: colors.inputBg, color: colors.text }]}
            value={name} onChangeText={setName}
            placeholder="e.g. Fidelity Brokerage" placeholderTextColor={colors.textTertiary} autoFocus
          />
          <Text style={[s.label, { color: colors.textSecondary }]}>Account type</Text>
          <ScrollView horizontal showsHorizontalScrollIndicator={false} style={{ marginBottom: 16 }}>
            <View style={s.pillRow}>
              {ACCOUNT_TYPES.map((t) => (
                <TouchableOpacity
                  key={t}
                  style={[s.pill, { backgroundColor: accountType === t ? colors.accent : colors.cardElevated }]}
                  onPress={() => setAccountType(t)}
                >
                  <Text style={[s.pillText, { color: accountType === t ? "#fff" : colors.textSecondary }]}>{t}</Text>
                </TouchableOpacity>
              ))}
            </View>
          </ScrollView>
          <TouchableOpacity
            style={[s.submitBtn, { backgroundColor: colors.accent }, saving && s.disabled]}
            onPress={handleSave} disabled={saving}
          >
            {saving ? <ActivityIndicator color="#fff" /> : <Text style={s.submitText}>Add Account</Text>}
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
  pillRow: { flexDirection: "row", gap: 8 },
  pill: { borderRadius: 20, paddingHorizontal: 14, paddingVertical: 8 },
  pillText: { fontSize: 14, fontWeight: "500" },
  submitBtn: { borderRadius: 12, paddingVertical: 14, alignItems: "center", marginBottom: 10 },
  disabled: { opacity: 0.6 },
  submitText: { color: "#fff", fontSize: 16, fontWeight: "600" },
  cancelBtn: { alignItems: "center", paddingVertical: 10 },
  cancelText: { fontSize: 15 },
});
