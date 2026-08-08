import React, { useRef } from "react";
import { View, Text, Animated, PanResponder, StyleSheet, TouchableOpacity } from "react-native";
import type { Meal } from "../lib/api";
import type { Colors } from "../lib/theme";

interface Props {
  meal: Meal;
  onDelete: (id: number) => void;
  colors: Colors;
}

const SWIPE_THRESHOLD = -80;

export function MealRow({ meal, onDelete, colors }: Props) {
  const translateX = useRef(new Animated.Value(0)).current;
  const deleteOpacity = translateX.interpolate({
    inputRange: [SWIPE_THRESHOLD, 0],
    outputRange: [1, 0],
    extrapolate: "clamp",
  });

  const panResponder = PanResponder.create({
    onMoveShouldSetPanResponder: (_, { dx }) => Math.abs(dx) > 10,
    onPanResponderMove: (_, { dx }) => { if (dx < 0) translateX.setValue(dx); },
    onPanResponderRelease: (_, { dx }) => {
      if (dx < SWIPE_THRESHOLD) {
        Animated.timing(translateX, { toValue: -120, duration: 150, useNativeDriver: true }).start(
          () => { if (meal?.id != null) onDelete(meal.id); }
        );
      } else {
        Animated.spring(translateX, { toValue: 0, useNativeDriver: true }).start();
      }
    },
  });

  const formatTime = (iso: string | null | undefined) => {
    if (!iso) return "";
    // SQLite stores UTC with no Z — append it so JS doesn't misread as local time
    const s = iso.includes("Z") || iso.includes("+") ? iso : iso.replace(" ", "T") + "Z";
    const d = new Date(s);
    if (isNaN(d.getTime())) return "";
    return d.toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit" });
  };

  return (
    <View style={styles.container}>
      <TouchableOpacity
        style={[styles.deleteBackground, { backgroundColor: colors.swipeDelete }]}
        onPress={() => { if (meal?.id != null) onDelete(meal.id); }}
        activeOpacity={0.8}
      >
        <Animated.View style={{ opacity: deleteOpacity, alignItems: "center" }}>
          <Text style={styles.deleteLabel}>Delete</Text>
        </Animated.View>
      </TouchableOpacity>
      <Animated.View
        style={[styles.row, { transform: [{ translateX }], backgroundColor: colors.background, borderBottomColor: colors.border }]}
        {...panResponder.panHandlers}
      >
        <View style={styles.info}>
          <Text style={[styles.desc, { color: colors.text }]}>{meal.description}</Text>
          <Text style={[styles.time, { color: colors.textSecondary }]}>{formatTime(meal.logged_at)}</Text>
        </View>
        <Text style={[styles.kcal, { color: colors.accentOrange }]}>{meal.calories} kcal</Text>
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
    paddingVertical: 10, paddingHorizontal: 4,
    borderBottomWidth: StyleSheet.hairlineWidth,
  },
  info: { flex: 1, marginRight: 12 },
  desc: { fontSize: 14 },
  time: { fontSize: 12, marginTop: 2 },
  kcal: { fontSize: 14, fontWeight: "600" },
});
