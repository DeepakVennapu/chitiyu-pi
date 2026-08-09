import React from "react";
import { StyleSheet, Text, View } from "react-native";
import type { Meal } from "../lib/api";
import { useTheme } from "../lib/theme";
import { SwipeableRow } from "./SwipeableRow";
import { formatTime } from "../lib/dateUtils";

interface Props {
  meal: Meal;
  onDelete: (id: number) => void;
}

export function MealRow({ meal, onDelete }: Props) {
  const { colors } = useTheme();

  const macros = [
    meal.protein != null && `P ${Math.round(meal.protein)}g`,
    meal.fat != null     && `F ${Math.round(meal.fat)}g`,
    meal.carbs != null   && `C ${Math.round(meal.carbs)}g`,
  ].filter(Boolean).join("  ");

  return (
    <SwipeableRow
      confirmTitle="Delete meal?"
      confirmMessage={meal.description}
      onDelete={() => onDelete(meal.id)}
      backgroundColor={colors.card}
    >
      <View style={[styles.row, { borderBottomColor: colors.border }]}>
        <View style={styles.info}>
          <Text style={[styles.desc, { color: colors.text }]} numberOfLines={1}>
            {meal.description}
          </Text>
          <Text style={[styles.sub, { color: colors.textSecondary }]}>
            {formatTime(meal.logged_at)}{macros ? `  ·  ${macros}` : ""}
          </Text>
        </View>
        <Text style={[styles.kcal, { color: colors.accentOrange }]}>{meal.calories} kcal</Text>
      </View>
    </SwipeableRow>
  );
}

const styles = StyleSheet.create({
  row: {
    flex: 1, flexDirection: "row", justifyContent: "space-between", alignItems: "center",
    paddingVertical: 12, paddingHorizontal: 16, borderBottomWidth: StyleSheet.hairlineWidth,
  },
  info: { flex: 1, marginRight: 12 },
  desc: { fontSize: 14 },
  sub: { fontSize: 12, marginTop: 2 },
  kcal: { fontSize: 14, fontWeight: "600" },
});
