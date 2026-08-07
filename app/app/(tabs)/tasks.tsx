import React, { useState, useEffect, useCallback } from "react";
import {
  View,
  Text,
  ScrollView,
  TouchableOpacity,
  Modal,
  TextInput,
  ActivityIndicator,
  RefreshControl,
  StyleSheet,
  SafeAreaView,
  KeyboardAvoidingView,
  Platform,
} from "react-native";
import { TaskRow } from "../../components/TaskRow";
import {
  getTasksOverdue,
  getTasksToday,
  addTask,
  completeTask,
  deleteTask,
  type Task,
} from "../../lib/api";
import { useTheme } from "../../lib/theme";

export default function TasksScreen() {
  const { colors } = useTheme();
  const [overdue, setOverdue] = useState<Task[]>([]);
  const [today, setToday] = useState<Task[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [sheetVisible, setSheetVisible] = useState(false);
  const [taskInput, setTaskInput] = useState("");
  const [adding, setAdding] = useState(false);

  const loadData = useCallback(async () => {
    setError(null);
    try {
      // Both endpoints return plain Task[] arrays (no wrapper object)
      const [overdueData, todayData] = await Promise.all([
        getTasksOverdue(),
        getTasksToday(),
      ]);
      setOverdue(overdueData);
      setToday(todayData);
    } catch (e: any) {
      setError(e?.message ?? "Failed to load tasks");
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => { loadData(); }, [loadData]);

  const handleRefresh = () => { setRefreshing(true); loadData(); };

  const handleAddTask = async () => {
    if (!taskInput.trim()) return;
    setAdding(true);
    try {
      const task = await addTask(taskInput.trim());
      // If due today, add to today section; otherwise no-op (user can refresh)
      setToday((prev) => [...prev, task]);
      setTaskInput("");
      setSheetVisible(false);
    } finally {
      setAdding(false);
    }
  };

  const handleComplete = async (id: number) => {
    await completeTask(id);
    setOverdue((prev) => prev.filter((t) => t.id !== id));
    setToday((prev) => prev.filter((t) => t.id !== id));
  };

  const handleDelete = async (id: number) => {
    await deleteTask(id);
    setOverdue((prev) => prev.filter((t) => t.id !== id));
    setToday((prev) => prev.filter((t) => t.id !== id));
  };

  if (loading) {
    return (
      <SafeAreaView style={[styles.safe, { backgroundColor: colors.background }]}>
        <View style={styles.center}><ActivityIndicator color={colors.accent} /></View>
      </SafeAreaView>
    );
  }

  if (error) {
    return (
      <SafeAreaView style={[styles.safe, { backgroundColor: colors.background }]}>
        <View style={styles.center}>
          <Text style={{ color: colors.accentRed, fontSize: 15, textAlign: "center", padding: 20 }}>{error}</Text>
        </View>
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={[styles.safe, { backgroundColor: colors.background }]}>
      <ScrollView
        style={styles.scroll}
        contentContainerStyle={styles.content}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={handleRefresh} />}
      >
        {/* Add Task CTA */}
        <TouchableOpacity
          style={[styles.primaryButton, { backgroundColor: colors.accent }]}
          onPress={() => setSheetVisible(true)}
        >
          <Text style={styles.primaryButtonText}>+ Add Task</Text>
        </TouchableOpacity>

        {/* Overdue section */}
        {overdue.length > 0 && (
          <View style={styles.section}>
            <View style={styles.sectionHeaderRow}>
              <Text style={[styles.sectionTitle, { color: colors.text }]}>Overdue</Text>
              <View style={[styles.badge, { backgroundColor: colors.accentRed }]}>
                <Text style={styles.badgeText}>{overdue.length}</Text>
              </View>
            </View>
            <View style={[styles.overdueContainer, { backgroundColor: colors.overdueStripe, borderLeftColor: colors.accentRed }]}>
              {overdue.map((task) => (
                <TaskRow
                  key={task.id}
                  task={task}
                  onComplete={handleComplete}
                  onDelete={handleDelete}
                />
              ))}
            </View>
          </View>
        )}

        {/* Today section */}
        <View style={styles.section}>
          <Text style={[styles.sectionTitle, { color: colors.text }]}>Today</Text>
          {today.length === 0 && overdue.length === 0 && (
            <Text style={{ color: colors.textSecondary, fontSize: 14 }}>All clear. Add a task above.</Text>
          )}
          {today.length === 0 && overdue.length > 0 && (
            <Text style={{ color: colors.textSecondary, fontSize: 14 }}>No tasks due today.</Text>
          )}
          {today.map((task) => (
            <TaskRow
              key={task.id}
              task={task}
              onComplete={handleComplete}
              onDelete={handleDelete}
            />
          ))}
        </View>
      </ScrollView>

      {/* Add Task Sheet */}
      <Modal
        visible={sheetVisible}
        transparent
        animationType="slide"
        onRequestClose={() => setSheetVisible(false)}
      >
        <KeyboardAvoidingView
          behavior={Platform.OS === "ios" ? "padding" : undefined}
          style={styles.modalOverlay}
        >
          <View style={[styles.modalSheet, { backgroundColor: colors.card }]}>
            <Text style={[styles.modalTitle, { color: colors.text }]}>Add Task</Text>
            <TextInput
              style={[styles.textInput, { backgroundColor: colors.cardElevated, color: colors.text }]}
              value={taskInput}
              onChangeText={setTaskInput}
              placeholder="e.g. Call doctor about blood work"
              placeholderTextColor={colors.textTertiary}
              autoFocus
              onSubmitEditing={handleAddTask}
              returnKeyType="done"
            />
            <TouchableOpacity
              style={[styles.submitButton, { backgroundColor: colors.accent }, adding && styles.buttonDisabled]}
              onPress={handleAddTask}
              disabled={adding}
            >
              {adding ? <ActivityIndicator color="#fff" /> : <Text style={styles.submitText}>Add Task</Text>}
            </TouchableOpacity>
            <TouchableOpacity style={styles.cancelButton} onPress={() => setSheetVisible(false)}>
              <Text style={[styles.cancelText, { color: colors.textSecondary }]}>Cancel</Text>
            </TouchableOpacity>
          </View>
        </KeyboardAvoidingView>
      </Modal>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1 },
  scroll: { flex: 1 },
  content: { padding: 16, paddingBottom: 40 },
  center: { flex: 1, alignItems: "center", justifyContent: "center" },
  primaryButton: {
    borderRadius: 12,
    paddingVertical: 14,
    alignItems: "center",
    marginBottom: 24,
  },
  primaryButtonText: { color: "#fff", fontSize: 16, fontWeight: "600" },
  section: { marginBottom: 28 },
  sectionHeaderRow: { flexDirection: "row", alignItems: "center", gap: 8, marginBottom: 10 },
  sectionTitle: { fontSize: 15, fontWeight: "600" },
  badge: {
    borderRadius: 10,
    paddingHorizontal: 7,
    paddingVertical: 1,
  },
  badgeText: { color: "#fff", fontSize: 11, fontWeight: "700" },
  overdueContainer: {
    borderRadius: 12,
    overflow: "hidden",
    borderLeftWidth: 3,
  },
  modalOverlay: { flex: 1, backgroundColor: "#00000088", justifyContent: "flex-end" },
  modalSheet: {
    borderTopLeftRadius: 20,
    borderTopRightRadius: 20,
    padding: 24,
    paddingBottom: 40,
  },
  modalTitle: { fontSize: 17, fontWeight: "600", marginBottom: 16 },
  textInput: {
    borderRadius: 10,
    padding: 14,
    fontSize: 15,
    marginBottom: 16,
  },
  submitButton: {
    borderRadius: 12,
    paddingVertical: 14,
    alignItems: "center",
    marginBottom: 10,
  },
  buttonDisabled: { opacity: 0.6 },
  submitText: { color: "#fff", fontSize: 16, fontWeight: "600" },
  cancelButton: { alignItems: "center", paddingVertical: 10 },
  cancelText: { fontSize: 15 },
});
