import React from "react";
import { StyleSheet, Text, View } from "react-native";
import type { Transaction } from "../lib/api";
import { useTheme } from "../lib/theme";
import { SwipeableRow } from "./SwipeableRow";

interface Props {
  transaction: Transaction;
  onDelete?: (id: number) => void;
}

export function TransactionRow({ transaction, onDelete }: Props) {
  const { colors } = useTheme();
  const isCredit = transaction.amount > 0;
  const formatted = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(
    Math.abs(transaction.amount)
  );
  const date = new Date(transaction.date + "T00:00:00").toLocaleDateString("en-US", {
    month: "short", day: "numeric",
  });

  const inner = (
    <View style={[styles.row, { borderBottomColor: colors.border }]}>
      <View style={styles.info}>
        <Text style={[styles.desc, { color: colors.text }]} numberOfLines={1}>
          {transaction.description}
        </Text>
        <Text style={[styles.meta, { color: colors.textSecondary }]}>
          {transaction.category.charAt(0).toUpperCase() + transaction.category.slice(1)} · {date}
        </Text>
      </View>
      <Text style={[styles.amount, { color: isCredit ? colors.accentGreen : colors.text }]}>
        {isCredit ? "+" : "-"}{formatted}
      </Text>
    </View>
  );

  if (!onDelete) return inner;

  return (
    <SwipeableRow
      confirmTitle="Delete transaction?"
      confirmMessage={transaction.description}
      onDelete={() => onDelete(transaction.id)}
      backgroundColor={colors.card}
    >
      {inner}
    </SwipeableRow>
  );
}

const styles = StyleSheet.create({
  row: {
    flex: 1, flexDirection: "row", justifyContent: "space-between", alignItems: "center",
    paddingVertical: 12, paddingHorizontal: 2, borderBottomWidth: StyleSheet.hairlineWidth,
  },
  info: { flex: 1, marginRight: 12 },
  desc: { fontSize: 14 },
  meta: { fontSize: 12, marginTop: 2 },
  amount: { fontSize: 14, fontWeight: "600" },
});
