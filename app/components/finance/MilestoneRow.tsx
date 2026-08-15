import React from "react";
import { View, Text, TouchableOpacity, StyleSheet } from "react-native";
import type { FinancialMilestone } from "../../lib/api";
import { useTheme } from "../../lib/theme";
import { fmt } from "../../lib/financeUtils";
import { todayLocal } from "../../lib/dateUtils";

interface Props {
  m: FinancialMilestone;
  onConfirm: (m: FinancialMilestone) => void;
}

export function MilestoneRow({ m, onConfirm }: Props) {
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
        ) : isPast ? (
          <TouchableOpacity
            style={[ms.confirmBtn, { backgroundColor: colors.accent + "22", borderColor: colors.accent }]}
            onPress={() => onConfirm(m)}
          >
            <Text style={[ms.confirmText, { color: colors.accent }]}>Confirm</Text>
          </TouchableOpacity>
        ) : (
          <Text style={[ms.pending, { color: colors.textTertiary }]}>upcoming</Text>
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
  pending: { fontSize: 12, color: "#999" },
  confirmBtn: { borderRadius: 6, borderWidth: 1, paddingHorizontal: 10, paddingVertical: 4 },
  confirmText: { fontSize: 12, fontWeight: "600" },
});
