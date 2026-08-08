import React from "react";
import { StyleSheet, Text, TouchableOpacity, View } from "react-native";
import type { Task } from "../lib/api";
import { useTheme } from "../lib/theme";
import { SwipeableRow } from "./SwipeableRow";

interface Props {
  task: Task;
  onComplete: (uid: string) => void;
  onDelete: (uid: string) => void;
}

const PRIORITY_COLORS: Record<number, string | null> = {
  0: null,
  1: "#FF9F0A",
  2: "#FF453A",
};

export function TaskRow({ task, onComplete, onDelete }: Props) {
  const { colors } = useTheme();
  const dotColor = PRIORITY_COLORS[task.priority] ?? null;

  const taskUid = task.uid ?? `t:${task.id}`;

  return (
    <SwipeableRow
      confirmTitle="Delete task?"
      confirmMessage={task.title}
      onDelete={() => onDelete(taskUid)}
      backgroundColor={colors.card}
    >
      <View style={[styles.row, { borderBottomColor: colors.border }]}>
        <TouchableOpacity
          style={styles.checkbox}
          onPress={() => onComplete(taskUid)}
          hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}
        >
          <View style={[styles.checkCircle, { borderColor: colors.checkCircle }]} />
        </TouchableOpacity>
        <View style={styles.info}>
          <View style={styles.titleRow}>
            {dotColor && (
              <View style={[styles.priorityDot, { backgroundColor: dotColor }]} />
            )}
            <Text style={[styles.title, { color: colors.text }]}>{task.title}</Text>
          </View>
          {task.due_at && (
            <Text style={[styles.due, { color: colors.textSecondary }]}>
              Due {new Date(task.due_at).toLocaleDateString("en-US", { month: "short", day: "numeric" })}
            </Text>
          )}
        </View>
      </View>
    </SwipeableRow>
  );
}

const styles = StyleSheet.create({
  row: {
    flex: 1, flexDirection: "row", alignItems: "center",
    paddingVertical: 12, paddingHorizontal: 4, borderBottomWidth: StyleSheet.hairlineWidth,
  },
  checkbox: { marginRight: 12 },
  checkCircle: { width: 22, height: 22, borderRadius: 11, borderWidth: 2 },
  info: { flex: 1 },
  titleRow: { flexDirection: "row", alignItems: "center", gap: 6 },
  priorityDot: { width: 8, height: 8, borderRadius: 4 },
  title: { fontSize: 15, flex: 1 },
  due: { fontSize: 12, marginTop: 2 },
});
