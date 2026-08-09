import React, { useState, useEffect, useCallback, useRef } from "react";
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
  FlatList,
} from "react-native";
import { TaskRow } from "../../components/TaskRow";
import {
  getTasksOverdue,
  getTasksToday,
  getTasksByDate,
  addTask,
  completeTask,
  deleteTask,
  type Task,
} from "../../lib/api";
import { useTheme } from "../../lib/theme";
import { todayLocal, dateToLocal } from "../../lib/dateUtils";

// ─── helpers ─────────────────────────────────────────────────────────────────

function addDays(d: Date, n: number) {
  const r = new Date(d);
  r.setDate(r.getDate() + n);
  return r;
}

function formatMonthYear(d: Date) {
  return d.toLocaleDateString("en-US", { month: "long", year: "numeric" });
}

function formatDayLabel(d: Date) {
  return d.toLocaleDateString("en-US", { weekday: "short" });
}

// Returns all days in the same month as d
function daysInMonth(d: Date): Date[] {
  const year = d.getFullYear();
  const month = d.getMonth();
  const count = new Date(year, month + 1, 0).getDate();
  return Array.from({ length: count }, (_, i) => new Date(year, month, i + 1));
}

// ─── CalendarPicker ──────────────────────────────────────────────────────────

interface CalendarPickerProps {
  selected: string; // YYYY-MM-DD
  onSelect: (iso: string) => void;
}

function CalendarPicker({ selected, onSelect }: CalendarPickerProps) {
  const { colors } = useTheme();
  const today = todayLocal();
  const [viewDate, setViewDate] = useState(() => new Date(selected || today));
  const days = daysInMonth(viewDate);
  const firstDow = new Date(viewDate.getFullYear(), viewDate.getMonth(), 1).getDay();
  const blanks = Array.from({ length: firstDow });

  return (
    <View style={calStyles.root}>
      <View style={calStyles.header}>
        <TouchableOpacity onPress={() => setViewDate((d) => addDays(new Date(d.getFullYear(), d.getMonth(), 1), -1))}>
          <Text style={[calStyles.navBtn, { color: colors.accent }]}>‹</Text>
        </TouchableOpacity>
        <Text style={[calStyles.monthLabel, { color: colors.text }]}>{formatMonthYear(viewDate)}</Text>
        <TouchableOpacity onPress={() => setViewDate((d) => new Date(d.getFullYear(), d.getMonth() + 1, 1))}>
          <Text style={[calStyles.navBtn, { color: colors.accent }]}>›</Text>
        </TouchableOpacity>
      </View>
      <View style={calStyles.dowRow}>
        {["Su", "Mo", "Tu", "We", "Th", "Fr", "Sa"].map((d) => (
          <Text key={d} style={[calStyles.dowLabel, { color: colors.textTertiary }]}>{d}</Text>
        ))}
      </View>
      <View style={calStyles.grid}>
        {blanks.map((_, i) => <View key={`b${i}`} style={calStyles.cell} />)}
        {days.map((d) => {
          const iso = dateToLocal(d);
          const isSelected = iso === selected;
          const isToday = iso === today;
          return (
            <TouchableOpacity
              key={iso}
              style={[
                calStyles.cell,
                isSelected && { backgroundColor: colors.accent, borderRadius: 16 },
                !isSelected && isToday && { borderRadius: 16, borderWidth: 1, borderColor: colors.accent },
              ]}
              onPress={() => onSelect(iso)}
            >
              <Text style={[
                calStyles.dayNum,
                { color: isSelected ? "#fff" : isToday ? colors.accent : colors.text },
              ]}>{d.getDate()}</Text>
            </TouchableOpacity>
          );
        })}
      </View>
    </View>
  );
}

const calStyles = StyleSheet.create({
  root: { marginBottom: 4 },
  header: { flexDirection: "row", justifyContent: "space-between", alignItems: "center", marginBottom: 8 },
  navBtn: { fontSize: 24, paddingHorizontal: 8 },
  monthLabel: { fontSize: 15, fontWeight: "600" },
  dowRow: { flexDirection: "row" },
  dowLabel: { flex: 1, textAlign: "center", fontSize: 11, marginBottom: 4 },
  grid: { flexDirection: "row", flexWrap: "wrap" },
  cell: { width: "14.28%", aspectRatio: 1, alignItems: "center", justifyContent: "center" },
  dayNum: { fontSize: 14 },
});

// ─── DayStrip ────────────────────────────────────────────────────────────────

interface DayStripProps {
  selected: string; // YYYY-MM-DD or "overdue"
  onSelect: (iso: string) => void;
  onOpenCalendar: () => void;
}

function DayStrip({ selected, onSelect, onOpenCalendar }: DayStripProps) {
  const { colors } = useTheme();
  const today = new Date();
  const days = Array.from({ length: 14 }, (_, i) => addDays(today, i - 0));
  const flatRef = useRef<FlatList>(null);

  useEffect(() => {
    const idx = days.findIndex((d) => dateToLocal(d) === selected);
    if (idx >= 0) flatRef.current?.scrollToIndex({ index: idx, animated: true, viewPosition: 0.5 });
  }, [selected]);

  return (
    <View style={stripStyles.row}>
      <FlatList
        ref={flatRef}
        horizontal
        showsHorizontalScrollIndicator={false}
        data={days}
        keyExtractor={(d) => dateToLocal(d)}
        contentContainerStyle={{ paddingHorizontal: 4 }}
        renderItem={({ item: d }) => {
          const iso = dateToLocal(d);
          const isSelected = iso === selected;
          return (
            <TouchableOpacity
              style={[
                stripStyles.dayBtn,
                { backgroundColor: isSelected ? colors.accent : colors.card },
              ]}
              onPress={() => onSelect(iso)}
            >
              <Text style={[stripStyles.dowText, { color: isSelected ? "#fff" : colors.textSecondary }]}>
                {formatDayLabel(d)}
              </Text>
              <Text style={[stripStyles.numText, { color: isSelected ? "#fff" : colors.text }]}>
                {d.getDate()}
              </Text>
            </TouchableOpacity>
          );
        }}
      />
      <TouchableOpacity style={[stripStyles.calBtn, { backgroundColor: colors.card }]} onPress={onOpenCalendar}>
        <Text style={{ color: colors.accent, fontSize: 18 }}>📅</Text>
      </TouchableOpacity>
    </View>
  );
}

const stripStyles = StyleSheet.create({
  row: { flexDirection: "row", alignItems: "center", marginBottom: 16, gap: 6 },
  dayBtn: { borderRadius: 10, paddingHorizontal: 10, paddingVertical: 8, alignItems: "center", marginRight: 6, minWidth: 46 },
  dowText: { fontSize: 11 },
  numText: { fontSize: 16, fontWeight: "600", marginTop: 2 },
  calBtn: { borderRadius: 10, padding: 8 },
});

// ─── Main screen ─────────────────────────────────────────────────────────────

export default function TasksScreen() {
  const { colors } = useTheme();
  const todayISO = todayLocal();
  const [selectedDate, setSelectedDate] = useState<string>(todayISO);
  const [calendarVisible, setCalendarVisible] = useState(false);
  const [overdue, setOverdue] = useState<Task[]>([]);
  const [dateTasks, setDateTasks] = useState<Task[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [sheetVisible, setSheetVisible] = useState(false);
  const [taskInput, setTaskInput] = useState("");
  const [dueDate, setDueDate] = useState<string>("");
  const [showDueDatePicker, setShowDueDatePicker] = useState(false);
  const [adding, setAdding] = useState(false);

  const isToday = selectedDate === todayISO;

  const loadData = useCallback(async () => {
    setError(null);
    try {
      if (isToday) {
        const [overdueData, todayData] = await Promise.all([
          getTasksOverdue(),
          getTasksToday(),
        ]);
        setOverdue(overdueData);
        setDateTasks(todayData);
      } else {
        const [overdueData, dateData] = await Promise.all([
          getTasksOverdue(),
          getTasksByDate(selectedDate),
        ]);
        setOverdue(overdueData);
        setDateTasks(dateData);
      }
    } catch (e: any) {
      setError(e?.message ?? "Failed to load tasks");
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [selectedDate, isToday]);

  useEffect(() => { loadData(); }, [loadData]);

  const handleRefresh = () => { setRefreshing(true); loadData(); };

  const handleAddTask = async () => {
    if (!taskInput.trim()) return;
    setAdding(true);
    try {
      const task = await addTask(taskInput.trim(), dueDate || undefined);
      if (!dueDate || dueDate === selectedDate) {
        setDateTasks((prev) => [...prev, task]);
      }
      setTaskInput("");
      setDueDate(selectedDate);
      setSheetVisible(false);
    } finally {
      setAdding(false);
    }
  };

  const handleComplete = async (id: number) => {
    await completeTask(id);
    setOverdue((prev) => prev.filter((t) => t.id !== id));
    setDateTasks((prev) => prev.filter((t) => t.id !== id));
  };

  const handleDelete = async (id: number) => {
    await deleteTask(id);
    setOverdue((prev) => prev.filter((t) => t.id !== id));
    setDateTasks((prev) => prev.filter((t) => t.id !== id));
  };

  const handleSelectDate = (iso: string) => {
    setSelectedDate(iso);
    setCalendarVisible(false);
  };

  const selectedLabel = selectedDate === todayISO
    ? "Today"
    : new Date(selectedDate + "T00:00:00").toLocaleDateString("en-US", { weekday: "long", month: "short", day: "numeric" });

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
        {/* Day strip calendar */}
        <DayStrip
          selected={selectedDate}
          onSelect={setSelectedDate}
          onOpenCalendar={() => setCalendarVisible(true)}
        />

        {/* Add Task CTA */}
        <TouchableOpacity
          style={[styles.primaryButton, { backgroundColor: colors.accent }]}
          onPress={() => { setDueDate(selectedDate); setSheetVisible(true); }}
        >
          <Text style={styles.primaryButtonText}>+ Add Task</Text>
        </TouchableOpacity>

        {/* Overdue section — only shown on today */}
        {isToday && overdue.length > 0 && (
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

        {/* Selected date tasks */}
        <View style={styles.section}>
          <Text style={[styles.sectionTitle, { color: colors.text }]}>{selectedLabel}</Text>
          {dateTasks.length === 0 && (
            <Text style={{ color: colors.textSecondary, fontSize: 14 }}>No tasks for this day.</Text>
          )}
          {dateTasks.map((task) => (
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

            {/* Due date row */}
            <TouchableOpacity
              style={[styles.dueDateRow, { backgroundColor: colors.cardElevated }]}
              onPress={() => setShowDueDatePicker((v) => !v)}
            >
              <Text style={{ color: colors.textSecondary, fontSize: 14 }}>Due date</Text>
              <Text style={{ color: dueDate ? colors.accent : colors.textTertiary, fontSize: 14, fontWeight: "500" }}>
                {dueDate
                  ? new Date(dueDate + "T00:00:00").toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" })
                  : "Optional"}
              </Text>
            </TouchableOpacity>

            {showDueDatePicker && (
              <View style={[styles.calendarBox, { backgroundColor: colors.cardElevated }]}>
                <CalendarPicker
                  selected={dueDate || todayLocal()}
                  onSelect={(iso) => { setDueDate(iso); setShowDueDatePicker(false); }}
                />
                {dueDate ? (
                  <TouchableOpacity onPress={() => setDueDate("")} style={styles.clearDueBtn}>
                    <Text style={{ color: colors.accentRed, fontSize: 13 }}>Clear date</Text>
                  </TouchableOpacity>
                ) : null}
              </View>
            )}

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

      {/* Full calendar modal */}
      <Modal
        visible={calendarVisible}
        transparent
        animationType="slide"
        onRequestClose={() => setCalendarVisible(false)}
      >
        <View style={styles.modalOverlay}>
          <View style={[styles.modalSheet, { backgroundColor: colors.card }]}>
            <Text style={[styles.modalTitle, { color: colors.text }]}>Pick a Day</Text>
            <CalendarPicker selected={selectedDate} onSelect={handleSelectDate} />
            <TouchableOpacity style={styles.cancelButton} onPress={() => setCalendarVisible(false)}>
              <Text style={[styles.cancelText, { color: colors.textSecondary }]}>Cancel</Text>
            </TouchableOpacity>
          </View>
        </View>
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
  badge: { borderRadius: 10, paddingHorizontal: 7, paddingVertical: 1 },
  badgeText: { color: "#fff", fontSize: 11, fontWeight: "700" },
  overdueContainer: { borderRadius: 12, overflow: "hidden", borderLeftWidth: 3 },
  modalOverlay: { flex: 1, backgroundColor: "#00000088", justifyContent: "flex-end" },
  modalSheet: { borderTopLeftRadius: 20, borderTopRightRadius: 20, padding: 24, paddingBottom: 40 },
  modalTitle: { fontSize: 17, fontWeight: "600", marginBottom: 16 },
  textInput: { borderRadius: 10, padding: 14, fontSize: 15, marginBottom: 12 },
  dueDateRow: {
    flexDirection: "row", justifyContent: "space-between", alignItems: "center",
    borderRadius: 10, paddingHorizontal: 14, paddingVertical: 12, marginBottom: 12,
  },
  calendarBox: { borderRadius: 12, padding: 12, marginBottom: 12 },
  clearDueBtn: { alignItems: "center", paddingTop: 4 },
  submitButton: { borderRadius: 12, paddingVertical: 14, alignItems: "center", marginBottom: 10 },
  buttonDisabled: { opacity: 0.6 },
  submitText: { color: "#fff", fontSize: 16, fontWeight: "600" },
  cancelButton: { alignItems: "center", paddingVertical: 10 },
  cancelText: { fontSize: 15 },
});
