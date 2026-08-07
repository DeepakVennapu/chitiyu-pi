import React, { useRef } from "react";
import { View, Text, TouchableOpacity, Animated, PanResponder, StyleSheet } from "react-native";
import type { Task } from "../lib/api";
import { useTheme } from "../lib/theme";

interface Props {
  task: Task;
  onComplete: (id: number) => void;
  onDelete: (id: number) => void;
}

const SWIPE_THRESHOLD = -80;

export function TaskRow({ task, onComplete, onDelete }: Props) {
  const { colors } = useTheme();
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
          () => onDelete(task.id)
        );
      } else {
        Animated.spring(translateX, { toValue: 0, useNativeDriver: true }).start();
      }
    },
  });

  return (
    <View style={styles.container}>
      <Animated.View style={[styles.deleteBackground, { opacity: deleteOpacity, backgroundColor: colors.swipeDelete }]}>
        <Text style={styles.deleteLabel}>Delete</Text>
      </Animated.View>
      <Animated.View
        style={[styles.row, { transform: [{ translateX }], backgroundColor: colors.background, borderBottomColor: colors.border }]}
        {...panResponder.panHandlers}
      >
        <TouchableOpacity style={styles.checkbox} onPress={() => onComplete(task.id)} hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}>
          <View style={[styles.checkCircle, { borderColor: colors.checkCircle }]} />
        </TouchableOpacity>
        <View style={styles.info}>
          <Text style={[styles.title, { color: colors.text }]}>{task.title}</Text>
          {task.due_at && (
            <Text style={[styles.due, { color: colors.textSecondary }]}>
              Due {new Date(task.due_at).toLocaleDateString("en-US", { month: "short", day: "numeric" })}
            </Text>
          )}
        </View>
      </Animated.View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { position: "relative", overflow: "hidden" },
  deleteBackground: { position: "absolute", right: 0, top: 0, bottom: 0, width: 120, alignItems: "center", justifyContent: "center" },
  deleteLabel: { color: "#fff", fontWeight: "600", fontSize: 14 },
  row: { flexDirection: "row", alignItems: "center", paddingVertical: 12, paddingHorizontal: 4, borderBottomWidth: StyleSheet.hairlineWidth },
  checkbox: { marginRight: 12 },
  checkCircle: { width: 22, height: 22, borderRadius: 11, borderWidth: 2 },
  info: { flex: 1 },
  title: { fontSize: 15 },
  due: { fontSize: 12, marginTop: 2 },
});
