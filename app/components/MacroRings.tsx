import React from "react";
import { View, Text, StyleSheet } from "react-native";
import type { MealTotals } from "../lib/api";
import { TARGETS } from "../constants/targets";
import { useTheme } from "../lib/theme";

interface Props { totals: MealTotals; }

export function MacroRings({ totals }: Props) {
  const { colors } = useTheme();
  const rings = [
    { label: "Protein", value: totals.protein, target: TARGETS.protein, color: colors.accentGreen },
    { label: "Fat", value: totals.fat, target: TARGETS.fat, color: colors.accentOrange },
    { label: "Carbs", value: totals.carbs, target: TARGETS.carbs, color: colors.accentPurple },
  ];

  return (
    <View style={styles.row}>
      {rings.map((ring) => {
        const pct = Math.min(ring.value / ring.target, 1);
        const over = ring.value > ring.target;
        return (
          <View key={ring.label} style={styles.ring}>
            <View style={[styles.circle, { borderColor: over ? colors.accentRed : ring.color, backgroundColor: colors.cardElevated }]}>
              <View style={[styles.fill, { height: `${pct * 100}%` as `${number}%`, backgroundColor: over ? colors.accentRed + "33" : ring.color + "33" }]} />
            </View>
            <Text style={[styles.value, { color: colors.text }]}>{Math.round(ring.value)}g</Text>
            <Text style={[styles.label, { color: colors.textSecondary }]}>{ring.label}</Text>
          </View>
        );
      })}
    </View>
  );
}

const styles = StyleSheet.create({
  row: { flexDirection: "row", justifyContent: "space-around", marginBottom: 20 },
  ring: { alignItems: "center", gap: 4 },
  circle: { width: 72, height: 72, borderRadius: 36, borderWidth: 3, overflow: "hidden", justifyContent: "flex-end" },
  fill: { width: "100%" },
  value: { fontSize: 14, fontWeight: "600" },
  label: { fontSize: 11 },
});
