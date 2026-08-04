import React from "react";
import { View, Text, StyleSheet } from "react-native";
import type { Transaction } from "../lib/api";

interface Props {
  transaction: Transaction;
}

export function TransactionRow({ transaction }: Props) {
  const isCredit = transaction.amount > 0;
  const formatted = new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
  }).format(Math.abs(transaction.amount));

  const date = new Date(transaction.date).toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
  });

  return (
    <View style={styles.row}>
      <View style={styles.info}>
        <Text style={styles.desc}>{transaction.description}</Text>
        <Text style={styles.meta}>
          {transaction.category} · {date}
        </Text>
      </View>
      <Text style={[styles.amount, isCredit ? styles.credit : styles.debit]}>
        {isCredit ? "+" : "-"}{formatted}
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  row: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    paddingVertical: 12,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: "#2C2C2E",
  },
  info: { flex: 1, marginRight: 12 },
  desc: { color: "#fff", fontSize: 14 },
  meta: { color: "#8E8E93", fontSize: 12, marginTop: 2 },
  amount: { fontSize: 14, fontWeight: "600" },
  credit: { color: "#30D158" },
  debit: { color: "#EBEBF5CC" },
});
