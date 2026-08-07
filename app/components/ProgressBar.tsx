import React from "react";
import { View, Text, StyleSheet } from "react-native";
import { useTheme } from "../lib/theme";

interface Props {
  label: string;
  value: number;
  target: number;
  unit: string;
  color?: string;
  formatter?: (n: number) => string;
}

export function ProgressBar({ label, value, target, unit, color, formatter }: Props) {
  const { colors } = useTheme();
  const trackColor = color ?? colors.accent;
  const pct = target > 0 ? Math.min(value / target, 1) : 0;
  const over = value > target;
  const fmt = formatter ?? ((n: number) => `${Math.round(n)}${unit}`);

  return (
    <View style={styles.container}>
      <View style={styles.labelRow}>
        <Text style={[styles.label, { color: colors.textSecondary }]}>{label}</Text>
        <Text style={[styles.value, { color: over ? colors.accentRed : colors.text }]}>
          {fmt(value)}
          <Text style={{ color: colors.textSecondary, fontWeight: "400" }}> / {fmt(target)}</Text>
        </Text>
      </View>
      <View style={[styles.track, { backgroundColor: colors.border }]}>
        <View style={[styles.fill, { width: `${pct * 100}%` as `${number}%`, backgroundColor: over ? colors.accentRed : trackColor }]} />
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { marginBottom: 14 },
  labelRow: { flexDirection: "row", justifyContent: "space-between", marginBottom: 5 },
  label: { fontSize: 13 },
  value: { fontSize: 13, fontWeight: "600" },
  track: { height: 6, borderRadius: 3, overflow: "hidden" },
  fill: { height: "100%", borderRadius: 3 },
});
