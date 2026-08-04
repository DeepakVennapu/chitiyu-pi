import React from "react";
import { View, Text, StyleSheet } from "react-native";
import type { InsightCard as InsightCardData } from "../lib/api";

interface Props {
  insight: InsightCardData;
}

export function InsightCard({ insight }: Props) {
  return (
    <View style={styles.card}>
      <Text style={styles.title}>{insight.title}</Text>
      <Text style={styles.fact}>{insight.fact}</Text>
      <Text style={styles.why}>{insight.why}</Text>
      <View style={styles.actionRow}>
        <Text style={styles.arrow}>→</Text>
        <Text style={styles.action}>{insight.action}</Text>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: "#1C1C1E",
    borderRadius: 12,
    padding: 16,
    marginBottom: 12,
    borderLeftWidth: 3,
    borderLeftColor: "#007AFF",
  },
  title: {
    color: "#fff",
    fontSize: 15,
    fontWeight: "600",
    marginBottom: 6,
  },
  fact: {
    color: "#EBEBF5CC",
    fontSize: 14,
    lineHeight: 20,
    marginBottom: 4,
  },
  why: {
    color: "#8E8E93",
    fontSize: 13,
    lineHeight: 18,
    marginBottom: 10,
  },
  actionRow: {
    flexDirection: "row",
    alignItems: "flex-start",
    gap: 6,
  },
  arrow: {
    color: "#007AFF",
    fontSize: 14,
    fontWeight: "700",
  },
  action: {
    color: "#007AFF",
    fontSize: 14,
    fontWeight: "500",
    flex: 1,
  },
});
