import React from "react";
import { View, Text, StyleSheet } from "react-native";

interface Props {
  label: string;
  value: number;
  target: number;
  unit: string;
  color?: string;
  formatter?: (n: number) => string;
}

export function ProgressBar({ label, value, target, unit, color = "#007AFF", formatter }: Props) {
  const pct = target > 0 ? Math.min(value / target, 1) : 0;
  const over = value > target;
  const fmt = formatter ?? ((n: number) => `${Math.round(n)}${unit}`);

  return (
    <View style={styles.container}>
      <View style={styles.labelRow}>
        <Text style={styles.label}>{label}</Text>
        <Text style={[styles.value, over && styles.over]}>
          {fmt(value)}
          <Text style={styles.target}> / {fmt(target)}</Text>
        </Text>
      </View>
      <View style={styles.track}>
        <View
          style={[
            styles.fill,
            { width: `${pct * 100}%` as `${number}%`, backgroundColor: over ? "#FF453A" : color },
          ]}
        />
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { marginBottom: 14 },
  labelRow: { flexDirection: "row", justifyContent: "space-between", marginBottom: 5 },
  label: { color: "#EBEBF5CC", fontSize: 13 },
  value: { color: "#fff", fontSize: 13, fontWeight: "600" },
  over: { color: "#FF453A" },
  target: { color: "#8E8E93", fontWeight: "400" },
  track: { height: 6, backgroundColor: "#2C2C2E", borderRadius: 3, overflow: "hidden" },
  fill: { height: "100%", borderRadius: 3 },
});
