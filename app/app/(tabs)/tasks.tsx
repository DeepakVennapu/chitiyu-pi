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

export default function TasksScreen() {
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
      <SafeAreaView style={styles.safe}>
        <View style={styles.center}><ActivityIndicator color="#007AFF" /></View>
      </SafeAreaView>
    );
  }

  if (error) {
    return (
      <SafeAreaView style={styles.safe}>
        <View style={styles.center}>
          <Text style={styles.errorText}>{error}</Text>
        </View>
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={styles.safe}>
      <ScrollView
        style={styles.scroll}
        contentContainerStyle={styles.content}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={handleRefresh} />}
      >
        {/* Add Task CTA */}
        <TouchableOpacity
          style={styles.primaryButton}
          onPress={() => setSheetVisible(true)}
        >
          <Text style={styles.primaryButtonText}>+ Add Task</Text>
        </TouchableOpacity>

        {/* Overdue section */}
        {overdue.length > 0 && (
          <View style={styles.section}>
            <View style={styles.sectionHeaderRow}>
              <Text style={styles.sectionTitle}>Overdue</Text>
              <View style={styles.badge}>
                <Text style={styles.badgeText}>{overdue.length}</Text>
              </View>
            </View>
            <View style={styles.overdueContainer}>
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
          <Text style={styles.sectionTitle}>Today</Text>
          {today.length === 0 && overdue.length === 0 && (
            <Text style={styles.emptyText}>All clear. Add a task above.</Text>
          )}
          {today.length === 0 && overdue.length > 0 && (
            <Text style={styles.emptyText}>No tasks due today.</Text>
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
          <View style={styles.modalSheet}>
            <Text style={styles.modalTitle}>Add Task</Text>
            <TextInput
              style={styles.textInput}
              value={taskInput}
              onChangeText={setTaskInput}
              placeholder="e.g. Call doctor about blood work"
              placeholderTextColor="#636366"
              autoFocus
              onSubmitEditing={handleAddTask}
              returnKeyType="done"
            />
            <TouchableOpacity
              style={[styles.submitButton, adding && styles.buttonDisabled]}
              onPress={handleAddTask}
              disabled={adding}
            >
              {adding ? <ActivityIndicator color="#fff" /> : <Text style={styles.submitText}>Add Task</Text>}
            </TouchableOpacity>
            <TouchableOpacity style={styles.cancelButton} onPress={() => setSheetVisible(false)}>
              <Text style={styles.cancelText}>Cancel</Text>
            </TouchableOpacity>
          </View>
        </KeyboardAvoidingView>
      </Modal>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: "#000" },
  scroll: { flex: 1 },
  content: { padding: 16, paddingBottom: 40 },
  center: { flex: 1, alignItems: "center", justifyContent: "center" },
  primaryButton: {
    backgroundColor: "#007AFF",
    borderRadius: 12,
    paddingVertical: 14,
    alignItems: "center",
    marginBottom: 24,
  },
  primaryButtonText: { color: "#fff", fontSize: 16, fontWeight: "600" },
  section: { marginBottom: 28 },
  sectionHeaderRow: { flexDirection: "row", alignItems: "center", gap: 8, marginBottom: 10 },
  sectionTitle: { color: "#fff", fontSize: 15, fontWeight: "600" },
  badge: {
    backgroundColor: "#FF453A",
    borderRadius: 10,
    paddingHorizontal: 7,
    paddingVertical: 1,
  },
  badgeText: { color: "#fff", fontSize: 11, fontWeight: "700" },
  overdueContainer: {
    backgroundColor: "#1C0A0A",
    borderRadius: 12,
    overflow: "hidden",
    borderLeftWidth: 3,
    borderLeftColor: "#FF453A",
  },
  emptyText: { color: "#8E8E93", fontSize: 14 },
  errorText: { color: "#FF453A", fontSize: 15, textAlign: "center", padding: 20 },
  modalOverlay: { flex: 1, backgroundColor: "#00000088", justifyContent: "flex-end" },
  modalSheet: {
    backgroundColor: "#1C1C1E",
    borderTopLeftRadius: 20,
    borderTopRightRadius: 20,
    padding: 24,
    paddingBottom: 40,
  },
  modalTitle: { color: "#fff", fontSize: 17, fontWeight: "600", marginBottom: 16 },
  textInput: {
    backgroundColor: "#2C2C2E",
    borderRadius: 10,
    padding: 14,
    color: "#fff",
    fontSize: 15,
    marginBottom: 16,
  },
  submitButton: {
    backgroundColor: "#007AFF",
    borderRadius: 12,
    paddingVertical: 14,
    alignItems: "center",
    marginBottom: 10,
  },
  buttonDisabled: { opacity: 0.6 },
  submitText: { color: "#fff", fontSize: 16, fontWeight: "600" },
  cancelButton: { alignItems: "center", paddingVertical: 10 },
  cancelText: { color: "#8E8E93", fontSize: 15 },
});
