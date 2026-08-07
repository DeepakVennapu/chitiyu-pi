import React, { useState } from "react";
import { View, Text, TouchableOpacity, StyleSheet, LayoutAnimation, Platform, UIManager } from "react-native";
import type { InsightCard as InsightCardData } from "../lib/api";
import { useTheme } from "../lib/theme";

if (Platform.OS === "android" && UIManager.setLayoutAnimationEnabledExperimental) {
  UIManager.setLayoutAnimationEnabledExperimental(true);
}

interface Props {
  insight: InsightCardData;
  index: number;
  onDismiss: (index: number) => void;
}

const ACCENT_COLORS = ["#007AFF", "#30D158", "#FF9F0A", "#BF5AF2", "#32ADE6"];

export function InsightCard({ insight, index, onDismiss }: Props) {
  const [expanded, setExpanded] = useState(false);
  const { colors } = useTheme();
  const accentColor = ACCENT_COLORS[index % ACCENT_COLORS.length];

  const toggle = () => {
    LayoutAnimation.configureNext(LayoutAnimation.Presets.easeInEaseOut);
    setExpanded((e) => !e);
  };

  return (
    <View style={[styles.card, { backgroundColor: colors.card, borderLeftColor: accentColor }]}>
      {/* Header row — always visible */}
      <TouchableOpacity style={styles.headerRow} onPress={toggle} activeOpacity={0.7}>
        <Text style={[styles.title, { color: colors.text }]} numberOfLines={expanded ? undefined : 1}>
          {insight.title}
        </Text>
        <View style={styles.headerActions}>
          <Text style={[styles.chevron, { color: colors.textSecondary }]}>
            {expanded ? "▲" : "▼"}
          </Text>
          <TouchableOpacity
            hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}
            onPress={() => onDismiss(index)}
            style={styles.dismissBtn}
          >
            <Text style={[styles.dismissX, { color: colors.textTertiary }]}>✕</Text>
          </TouchableOpacity>
        </View>
      </TouchableOpacity>

      {/* Expanded body */}
      {expanded && (
        <View style={styles.body}>
          <Text style={[styles.fact, { color: colors.text }]}>{insight.fact}</Text>
          <Text style={[styles.why, { color: colors.textSecondary }]}>{insight.why}</Text>
          <View style={styles.actionRow}>
            <Text style={[styles.arrow, { color: accentColor }]}>→</Text>
            <Text style={[styles.action, { color: accentColor }]}>{insight.action}</Text>
          </View>
        </View>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    borderRadius: 12,
    marginBottom: 10,
    borderLeftWidth: 3,
    overflow: "hidden",
  },
  headerRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    padding: 14,
    gap: 8,
  },
  title: {
    fontSize: 14,
    fontWeight: "600",
    flex: 1,
  },
  headerActions: {
    flexDirection: "row",
    alignItems: "center",
    gap: 10,
  },
  chevron: { fontSize: 10 },
  dismissBtn: { padding: 2 },
  dismissX: { fontSize: 14, fontWeight: "600" },
  body: {
    paddingHorizontal: 14,
    paddingBottom: 14,
    gap: 6,
  },
  fact: { fontSize: 14, lineHeight: 20 },
  why: { fontSize: 13, lineHeight: 18 },
  actionRow: { flexDirection: "row", alignItems: "flex-start", gap: 6, marginTop: 4 },
  arrow: { fontSize: 14, fontWeight: "700" },
  action: { fontSize: 13, fontWeight: "500", flex: 1 },
});
