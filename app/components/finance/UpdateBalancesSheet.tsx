import React, { useState, useEffect } from "react";
import {
  Modal, View, Text, TextInput, TouchableOpacity, ScrollView,
  KeyboardAvoidingView, ActivityIndicator, Platform, StyleSheet, Alert,
} from "react-native";
import { updateBalances, type Account, type AccountBalance, type BalanceEntry } from "../../lib/api";
import { useTheme } from "../../lib/theme";
import { accountTypeOrder } from "../../lib/financeUtils";

interface Props {
  visible: boolean;
  accounts: Account[];
  balances: AccountBalance[];
  onClose: () => void;
  onSaved: (computedNetWorth: number | null) => void;
}

export function UpdateBalancesSheet({ visible, accounts, balances, onClose, onSaved }: Props) {
  const { colors } = useTheme();
  const [inputs, setInputs] = useState<Record<number, string>>({});
  const [lastUpdated, setLastUpdated] = useState<Record<number, string>>({});
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (visible) {
      const initial: Record<number, string> = {};
      const lastUpd: Record<number, string> = {};
      for (const b of balances) {
        initial[b.account_id] = String(Math.abs(b.balance));
        lastUpd[b.account_id] = b.date;
      }
      setInputs(initial);
      setLastUpdated(lastUpd);
    }
  }, [visible, balances]);

  const handleSave = async () => {
    const entries: BalanceEntry[] = [];
    for (const acct of accounts) {
      const raw = inputs[acct.id];
      const hasExisting = balances.some((b) => b.account_id === acct.id);
      if ((raw == null || raw.trim() === "") && !hasExisting) continue;
      const val = parseFloat(raw ?? "0") || 0;
      entries.push({ account_id: acct.id, balance: acct.type === "credit" ? -Math.abs(val) : val });
    }
    if (entries.length === 0) { onClose(); return; }
    setSaving(true);
    try {
      const res = await updateBalances(entries);
      onSaved(res.computed_net_worth);
    } catch (e: any) {
      Alert.alert("Couldn't save balances", e?.message ?? "Please try again.");
    } finally {
      setSaving(false);
    }
  };

  const sortedTypes = [...new Set(accounts.map((a) => a.type))].sort(
    (a, b) => accountTypeOrder(a) - accountTypeOrder(b)
  );

  return (
    <Modal visible={visible} transparent animationType="slide" onRequestClose={onClose}>
      <KeyboardAvoidingView behavior={Platform.OS === "ios" ? "padding" : "height"} style={s.overlay}>
        <ScrollView style={[s.sheet, { backgroundColor: colors.card }]} keyboardShouldPersistTaps="handled">
          <Text style={[s.title, { color: colors.text }]}>Update Balances</Text>
          <Text style={[s.hint, { color: colors.textSecondary }]}>
            Enter today's balances. Credit cards: enter the amount owed (we'll make it negative).
          </Text>
          {sortedTypes.map((type) => (
            <View key={type}>
              <Text style={[s.typeHeader, { color: colors.textTertiary }]}>{type.toUpperCase()}</Text>
              {accounts
                .filter((a) => a.type === type)
                .sort((a, b) => a.name.localeCompare(b.name))
                .map((acct) => (
                  <View key={acct.id} style={[s.row, { borderBottomColor: colors.border }]}>
                    <View style={{ flex: 1 }}>
                      <Text style={[s.label, { color: colors.text }]}>{acct.name}</Text>
                      {lastUpdated[acct.id] && (
                        <Text style={[s.date, { color: colors.textTertiary }]}>
                          Updated {new Date(lastUpdated[acct.id] + "T00:00:00").toLocaleDateString("en-US", { month: "short", day: "numeric" })}
                        </Text>
                      )}
                    </View>
                    <TextInput
                      style={[s.input, { backgroundColor: colors.inputBg, color: colors.text }]}
                      value={inputs[acct.id] ?? ""}
                      onChangeText={(v) => setInputs((prev) => ({ ...prev, [acct.id]: v }))}
                      placeholder="0"
                      placeholderTextColor={colors.textTertiary}
                      keyboardType="decimal-pad"
                    />
                  </View>
                ))}
            </View>
          ))}
          <TouchableOpacity
            style={[s.submitBtn, { backgroundColor: colors.accent, marginTop: 16 }, saving && s.disabled]}
            onPress={handleSave}
            disabled={saving}
          >
            {saving ? <ActivityIndicator color="#fff" /> : <Text style={s.submitText}>Save Balances</Text>}
          </TouchableOpacity>
          <TouchableOpacity style={s.cancelBtn} onPress={onClose}>
            <Text style={[s.cancelText, { color: colors.textSecondary }]}>Cancel</Text>
          </TouchableOpacity>
        </ScrollView>
      </KeyboardAvoidingView>
    </Modal>
  );
}

const s = StyleSheet.create({
  overlay: { flex: 1, backgroundColor: "#00000088", justifyContent: "flex-end" },
  sheet: { maxHeight: "85%", borderTopLeftRadius: 20, borderTopRightRadius: 20, padding: 24 },
  title: { fontSize: 17, fontWeight: "600", marginBottom: 8 },
  hint: { fontSize: 12, marginBottom: 16 },
  typeHeader: { fontSize: 11, fontWeight: "600", letterSpacing: 0.8, marginTop: 10, marginBottom: 4 },
  row: { flexDirection: "row", alignItems: "center", paddingVertical: 8, borderBottomWidth: StyleSheet.hairlineWidth, gap: 12 },
  label: { fontSize: 14 },
  date: { fontSize: 11, marginTop: 2 },
  input: { width: 120, borderRadius: 8, padding: 10, fontSize: 14, textAlign: "right" },
  submitBtn: { borderRadius: 12, paddingVertical: 14, alignItems: "center", marginBottom: 10 },
  disabled: { opacity: 0.6 },
  submitText: { color: "#fff", fontSize: 16, fontWeight: "600" },
  cancelBtn: { alignItems: "center", paddingVertical: 10, marginBottom: 20 },
  cancelText: { fontSize: 15 },
});
