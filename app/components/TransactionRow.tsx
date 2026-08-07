import React, { useRef } from "react";
import { View, Text, TouchableOpacity, Animated, PanResponder, StyleSheet } from "react-native";
import type { Transaction } from "../lib/api";
import { useTheme } from "../lib/theme";

interface Props {
  transaction: Transaction;
  onDelete?: (id: number) => void;
}

const SWIPE_THRESHOLD = -80;

export function TransactionRow({ transaction, onDelete }: Props) {
  const { colors } = useTheme();
  const translateX = useRef(new Animated.Value(0)).current;
  const deleteOpacity = translateX.interpolate({
    inputRange: [SWIPE_THRESHOLD, 0],
    outputRange: [1, 0],
    extrapolate: "clamp",
  });

  const panResponder = PanResponder.create({
    onMoveShouldSetPanResponder: (_, { dx }) => onDelete != null && Math.abs(dx) > 10,
    onPanResponderMove: (_, { dx }) => { if (dx < 0) translateX.setValue(dx); },
    onPanResponderRelease: (_, { dx }) => {
      if (dx < SWIPE_THRESHOLD && onDelete) {
        Animated.timing(translateX, { toValue: -120, duration: 150, useNativeDriver: true }).start(
          () => onDelete(transaction.id)
        );
      } else {
        Animated.spring(translateX, { toValue: 0, useNativeDriver: true }).start();
      }
    },
  });

  const isCredit = transaction.amount > 0;
  const formatted = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(Math.abs(transaction.amount));
  const date = new Date(transaction.date).toLocaleDateString("en-US", { month: "short", day: "numeric" });

  return (
    <View style={styles.container}>
      {onDelete && (
        <Animated.View style={[styles.deleteBackground, { opacity: deleteOpacity, backgroundColor: colors.swipeDelete }]}>
          <Text style={styles.deleteLabel}>Delete</Text>
        </Animated.View>
      )}
      <Animated.View
        style={[styles.row, { transform: [{ translateX }], backgroundColor: colors.background, borderBottomColor: colors.border }]}
        {...(onDelete ? panResponder.panHandlers : {})}
      >
        <View style={styles.info}>
          <Text style={[styles.desc, { color: colors.text }]}>{transaction.description}</Text>
          <Text style={[styles.meta, { color: colors.textSecondary }]}>{transaction.category} · {date}</Text>
        </View>
        <Text style={[styles.amount, { color: isCredit ? colors.accentGreen : colors.text }]}>
          {isCredit ? "+" : "-"}{formatted}
        </Text>
      </Animated.View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { position: "relative", overflow: "hidden" },
  deleteBackground: {
    position: "absolute", right: 0, top: 0, bottom: 0, width: 120,
    alignItems: "center", justifyContent: "center",
  },
  deleteLabel: { color: "#fff", fontWeight: "600", fontSize: 14 },
  row: {
    flexDirection: "row", justifyContent: "space-between", alignItems: "center",
    paddingVertical: 12, borderBottomWidth: StyleSheet.hairlineWidth,
  },
  info: { flex: 1, marginRight: 12 },
  desc: { fontSize: 14 },
  meta: { fontSize: 12, marginTop: 2 },
  amount: { fontSize: 14, fontWeight: "600" },
});
