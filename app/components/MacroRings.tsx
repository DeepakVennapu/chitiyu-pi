import React from "react";
import { View, Text, StyleSheet } from "react-native";
import type { MealTotals } from "../lib/api";
import { TARGETS } from "../constants/targets";

interface Props {
  totals: MealTotals;
}

interface Ring {
  label: string;
  value: number;
  target: number;
  color: string;
}

export function MacroRings({ totals }: Props) {
  const rings: Ring[] = [
    { label: "Protein", value: totals.protein, target: TARGETS.protein, color: "#30D158" },
    { label: "Fat", value: totals.fat, target: TARGETS.fat, color: "#FF9F0A" },
    { label: "Carbs", value: totals.carbs, target: TARGETS.carbs, color: "#BF5AF2" },
  ];

  return (
    <View style={styles.row}>
      {rings.map((ring) => {
        const pct = Math.min(ring.value / ring.target, 1);
        const over = ring.value > ring.target;
        return (
          <View key={ring.label} style={styles.ring}>
            <View style={[styles.circle, { borderColor: over ? "#FF453A" : ring.color }]}>
              <View
                style={[
                  styles.fill,
                  {
                    height: `${pct * 100}%` as `${number}%`,
                    backgroundColor: over ? "#FF453A33" : `${ring.color}33`,
                  },
                ]}
              />
            </View>
            <Text style={styles.value}>{Math.round(ring.value)}g</Text>
            <Text style={styles.label}>{ring.label}</Text>
          </View>
        );
      })}
    </View>
  );
}

const styles = StyleSheet.create({
  row: { flexDirection: "row", justifyContent: "space-around", marginBottom: 20 },
  ring: { alignItems: "center", gap: 4 },
  circle: {
    width: 72,
    height: 72,
    borderRadius: 36,
    borderWidth: 3,
    overflow: "hidden",
    justifyContent: "flex-end",
    backgroundColor: "#2C2C2E",
  },
  fill: { width: "100%" },
  value: { color: "#fff", fontSize: 14, fontWeight: "600" },
  label: { color: "#8E8E93", fontSize: 11 },
});
