import React from "react";
import { StyleSheet, Text, TouchableOpacity, View } from "react-native";
import type { Task } from "../lib/api";
import { useTheme } from "../lib/theme";
import { SwipeableRow } from "./SwipeableRow";

interface Props {
  task: Task;
  onComplete: (id: number) => void;
  onDelete: (id: number) => void;
}

export function TaskRow({ task, onComplete, onDelete }: Props) {
  const { colors } = useTheme();

  return (
    <SwipeableRow
      confirmTitle="Delete task?"
      confirmMessage={task.title}
      onDelete={() => onDelete(task.id)}
      backgroundColor={colors.card}
    >
      <View style={[styles.row, { borderBottomColor: colors.border }]}>
        <TouchableOpacity
          style={styles.checkbox}
          onPress={() => onComplete(task.id)}
          hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}
        >
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
  title: { fontSize: 15 },
  due: { fontSize: 12, marginTop: 2 },
});
