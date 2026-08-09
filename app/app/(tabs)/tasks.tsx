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
  completeInstance,
  deleteInstance,
  createTaskTemplate,
  getTasksDatesSummary,
  type Task,
} from "../../lib/api";
import { useTheme } from "../../lib/theme";

// ─── helpers ─────────────────────────────────────────────────────────────────

function toISO(d: Date) {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

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

function daysInMonth(d: Date): Date[] {
  const year = d.getFullYear();
  const month = d.getMonth();
  const count = new Date(year, month + 1, 0).getDate();
  return Array.from({ length: count }, (_, i) => new Date(year, month, i + 1));
}

// Priority dot color: 0=none, 1=yellow, 2=red
const INDICATOR_COLORS: Record<number, string> = {
  1: "#FF9F0A",
  2: "#FF453A",
};

// ─── CalendarPicker ──────────────────────────────────────────────────────────

interface CalendarPickerProps {
  selected: string;
  onSelect: (iso: string) => void;
  datesSummary?: Record<string, number>;
}

function CalendarPicker({ selected, onSelect, datesSummary = {} }: CalendarPickerProps) {
  const { colors } = useTheme();
  const today = toISO(new Date());
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
          const iso = toISO(d);
          const isSelected = iso === selected;
          const isToday = iso === today;
          const maxPriority = datesSummary[iso];
          const indicatorColor = maxPriority !== undefined ? (INDICATOR_COLORS[maxPriority] ?? colors.textTertiary) : null;
          return (
            <TouchableOpacity
              key={iso}
              style={[
                calStyles.cell,
                isSelected && { backgroundColor: colors.accent, borderRadius: 16 },
              ]}
              onPress={() => onSelect(iso)}
            >
              <Text style={[
                calStyles.dayNum,
                { color: isSelected ? "#fff" : isToday ? colors.accent : colors.text },
                isToday && !isSelected && { fontWeight: "700" },
              ]}>{d.getDate()}</Text>
              {indicatorColor ? (
                <View style={[calStyles.dot, { backgroundColor: indicatorColor }]} />
              ) : (
                <View style={calStyles.dotPlaceholder} />
              )}
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
  dot: { width: 5, height: 5, borderRadius: 3, marginTop: 2 },
  dotPlaceholder: { width: 5, height: 5, marginTop: 2 },
});

// ─── DayStrip ────────────────────────────────────────────────────────────────

interface DayStripProps {
  selected: string;
  onSelect: (iso: string) => void;
  onOpenCalendar: () => void;
  datesSummary: Record<string, number>;
}

function DayStrip({ selected, onSelect, onOpenCalendar, datesSummary }: DayStripProps) {
  const { colors } = useTheme();
  const today = new Date();
  const days = Array.from({ length: 14 }, (_, i) => addDays(today, i));
  const flatRef = useRef<FlatList>(null);
  const todayISO = toISO(new Date());

  useEffect(() => {
    const idx = days.findIndex((d) => toISO(d) === selected);
    if (idx >= 0) flatRef.current?.scrollToIndex({ index: idx, animated: true, viewPosition: 0.5 });
  }, [selected]);

  return (
    <View style={stripStyles.row}>
      <FlatList
        ref={flatRef}
        horizontal
        showsHorizontalScrollIndicator={false}
        data={days}
        keyExtractor={(d) => toISO(d)}
        contentContainerStyle={{ paddingHorizontal: 4 }}
        renderItem={({ item: d }) => {
          const iso = toISO(d);
          const isSelected = iso === selected;
          const isToday = iso === todayISO;
          const maxPriority = datesSummary[iso];
          const dotColor = maxPriority !== undefined ? (INDICATOR_COLORS[maxPriority] ?? "#8E8E93") : null;
          return (
            <TouchableOpacity
              style={[
                stripStyles.dayBtn,
                { backgroundColor: isSelected ? colors.accent : colors.card },
              ]}
              onPress={() => onSelect(iso)}
            >
              <Text style={[stripStyles.dowText, { color: isSelected ? "#fff" : isToday ? colors.accent : colors.textSecondary, fontWeight: isToday && !isSelected ? "700" : "400" }]}>
                {formatDayLabel(d)}
              </Text>
              <Text style={[stripStyles.numText, { color: isSelected ? "#fff" : isToday ? colors.accent : colors.text }]}>
                {d.getDate()}
              </Text>
              {dotColor ? (
                <View style={[stripStyles.dot, { backgroundColor: isSelected ? "rgba(255,255,255,0.7)" : dotColor }]} />
              ) : (
                <View style={stripStyles.dotPlaceholder} />
              )}
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
  dot: { width: 5, height: 5, borderRadius: 3, marginTop: 3 },
  dotPlaceholder: { width: 5, height: 5, marginTop: 3 },
  calBtn: { borderRadius: 10, padding: 8 },
});

// ─── Priority picker ─────────────────────────────────────────────────────────

interface PriorityPickerProps {
  value: number;
  onChange: (v: number) => void;
}

const PRIORITY_OPTIONS = [
  { value: 0, label: "Normal", color: null },
  { value: 1, label: "High", color: "#FF9F0A" },
  { value: 2, label: "Urgent", color: "#FF453A" },
];

function PriorityPicker({ value, onChange }: PriorityPickerProps) {
  const { colors } = useTheme();
  return (
    <View style={priorityStyles.row}>
      {PRIORITY_OPTIONS.map((opt) => {
        const isSelected = opt.value === value;
        return (
          <TouchableOpacity
            key={opt.value}
            style={[
              priorityStyles.option,
              { backgroundColor: isSelected ? (opt.color ?? colors.accent) : colors.cardElevated },
            ]}
            onPress={() => onChange(opt.value)}
          >
            {opt.color && <View style={[priorityStyles.dot, { backgroundColor: isSelected ? "#fff" : opt.color }]} />}
            <Text style={{ color: isSelected ? "#fff" : colors.textSecondary, fontSize: 13, fontWeight: "500" }}>
              {opt.label}
            </Text>
          </TouchableOpacity>
        );
      })}
    </View>
  );
}

const priorityStyles = StyleSheet.create({
  row: { flexDirection: "row", gap: 8, marginBottom: 12 },
  option: { flex: 1, flexDirection: "row", alignItems: "center", justifyContent: "center", gap: 5, borderRadius: 10, paddingVertical: 10 },
  dot: { width: 7, height: 7, borderRadius: 4 },
});

// ─── Recurrence picker ───────────────────────────────────────────────────────

type Recurrence = "none" | "daily" | "weekly" | "monthly" | "yearly";
const RECURRENCE_OPTIONS: { value: Recurrence; label: string }[] = [
  { value: "none", label: "None" },
  { value: "daily", label: "Daily" },
  { value: "weekly", label: "Weekly" },
  { value: "monthly", label: "Monthly" },
  { value: "yearly", label: "Yearly" },
];

interface RecurrencePickerProps {
  value: Recurrence;
  onChange: (v: Recurrence) => void;
}

function RecurrencePicker({ value, onChange }: RecurrencePickerProps) {
  const { colors } = useTheme();
  return (
    <ScrollView horizontal showsHorizontalScrollIndicator={false} style={{ marginBottom: 12 }}>
      <View style={{ flexDirection: "row", gap: 8 }}>
        {RECURRENCE_OPTIONS.map((opt) => {
          const isSelected = opt.value === value;
          return (
            <TouchableOpacity
              key={opt.value}
              style={[
                recStyles.chip,
                { backgroundColor: isSelected ? colors.accent : colors.cardElevated },
              ]}
              onPress={() => onChange(opt.value)}
            >
              <Text style={{ color: isSelected ? "#fff" : colors.textSecondary, fontSize: 13, fontWeight: "500" }}>
                {opt.label}
              </Text>
            </TouchableOpacity>
          );
        })}
      </View>
    </ScrollView>
  );
}

const recStyles = StyleSheet.create({
  chip: { borderRadius: 20, paddingHorizontal: 16, paddingVertical: 8 },
});

// ─── Main screen ─────────────────────────────────────────────────────────────

export default function TasksScreen() {
  const { colors } = useTheme();
  const todayISO = toISO(new Date());
  const [selectedDate, setSelectedDate] = useState<string>(todayISO);
  const [calendarVisible, setCalendarVisible] = useState(false);
  const [overdue, setOverdue] = useState<Task[]>([]);
  const [dateTasks, setDateTasks] = useState<Task[]>([]);
  const [datesSummary, setDatesSummary] = useState<Record<string, number>>({});
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [sheetVisible, setSheetVisible] = useState(false);
  const [taskInput, setTaskInput] = useState("");
  const [dueDate, setDueDate] = useState<string>("");
  const [showDueDatePicker, setShowDueDatePicker] = useState(false);
  const [priority, setPriority] = useState<number>(0);
  const [recurrence, setRecurrence] = useState<Recurrence>("none");
  const [showInAdvance, setShowInAdvance] = useState(false);
  const [adding, setAdding] = useState(false);

  const isToday = selectedDate === todayISO;

  const loadSummary = useCallback(async () => {
    const start = todayISO;
    const end = toISO(addDays(new Date(), 30));
    try {
      const summary = await getTasksDatesSummary(start, end);
      setDatesSummary(summary);
    } catch {
      // non-fatal
    }
  }, [todayISO]);

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

  useEffect(() => { loadData(); loadSummary(); }, [loadData]);

  const handleRefresh = () => { setRefreshing(true); loadData(); loadSummary(); };

  const openSheet = () => {
    setDueDate(selectedDate);
    setPriority(0);
    setRecurrence("none");
    setShowInAdvance(false);
    setShowDueDatePicker(false);
    setSheetVisible(true);
  };

  const handleAddTask = async () => {
    if (!taskInput.trim()) return;
    setAdding(true);
    try {
      if (recurrence !== "none") {
        const advance = showInAdvance ? 365 : undefined;
        await createTaskTemplate(taskInput.trim(), recurrence, dueDate || todayISO, advance);
        await loadData();
      } else {
        const task = await addTask(taskInput.trim(), dueDate || undefined, priority);
        if (!dueDate || dueDate === selectedDate) {
          setDateTasks((prev) => {
            const updated = [...prev, task];
            return updated.sort((a, b) => b.priority - a.priority);
          });
        }
      }
      setTaskInput("");
      setDueDate(selectedDate);
      setSheetVisible(false);
      loadSummary();
    } finally {
      setAdding(false);
    }
  };

  const handleComplete = async (uid: string) => {
    const task = [...overdue, ...dateTasks].find((t) => (t.uid ?? `t:${t.id}`) === uid);
    const numericId = parseInt(uid.split(":")[1]);
    if (task?.is_recurring) {
      await completeInstance(numericId);
    } else {
      await completeTask(numericId);
    }
    setOverdue((prev) => prev.filter((t) => (t.uid ?? `t:${t.id}`) !== uid));
    setDateTasks((prev) => prev.filter((t) => (t.uid ?? `t:${t.id}`) !== uid));
    loadSummary();
  };

  const handleDelete = async (uid: string) => {
    const task = [...overdue, ...dateTasks].find((t) => (t.uid ?? `t:${t.id}`) === uid);
    const numericId = parseInt(uid.split(":")[1]);
    if (task?.is_recurring) {
      await deleteInstance(numericId);
    } else {
      await deleteTask(numericId);
    }
    setOverdue((prev) => prev.filter((t) => (t.uid ?? `t:${t.id}`) !== uid));
    setDateTasks((prev) => prev.filter((t) => (t.uid ?? `t:${t.id}`) !== uid));
    loadSummary();
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
        <DayStrip
          selected={selectedDate}
          onSelect={setSelectedDate}
          onOpenCalendar={() => setCalendarVisible(true)}
          datesSummary={datesSummary}
        />

        <TouchableOpacity
          style={[styles.primaryButton, { backgroundColor: colors.accent }]}
          onPress={openSheet}
        >
          <Text style={styles.primaryButtonText}>+ Add Task</Text>
        </TouchableOpacity>

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
                <TaskRow key={task.uid ?? `t:${task.id}`} task={task} onComplete={handleComplete} onDelete={handleDelete} />
              ))}
            </View>
          </View>
        )}

        <View style={styles.section}>
          <Text style={[styles.sectionTitle, { color: colors.text }]}>{selectedLabel}</Text>
          {dateTasks.length === 0 && (
            <Text style={{ color: colors.textSecondary, fontSize: 14 }}>No tasks for this day.</Text>
          )}
          {dateTasks.map((task) => (
            <TaskRow key={task.uid ?? `t:${task.id}`} task={task} onComplete={handleComplete} onDelete={handleDelete} />
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

            {/* Priority */}
            <Text style={[styles.fieldLabel, { color: colors.textSecondary }]}>Priority</Text>
            <PriorityPicker value={priority} onChange={setPriority} />

            {/* Due date */}
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
                  selected={dueDate || toISO(new Date())}
                  onSelect={(iso) => { setDueDate(iso); setShowDueDatePicker(false); }}
                />
                {dueDate ? (
                  <TouchableOpacity onPress={() => setDueDate("")} style={styles.clearDueBtn}>
                    <Text style={{ color: colors.accentRed, fontSize: 13 }}>Clear date</Text>
                  </TouchableOpacity>
                ) : null}
              </View>
            )}

            {/* Repeat */}
            <Text style={[styles.fieldLabel, { color: colors.textSecondary }]}>Repeat</Text>
            <RecurrencePicker value={recurrence} onChange={setRecurrence} />

            {recurrence !== "none" && (
              <TouchableOpacity
                style={[styles.advanceRow, { backgroundColor: colors.cardElevated }]}
                onPress={() => setShowInAdvance((v) => !v)}
              >
                <Text style={{ color: colors.textSecondary, fontSize: 14 }}>Show in advance</Text>
                <View style={[styles.toggle, { backgroundColor: showInAdvance ? colors.accent : colors.borderSubtle }]}>
                  <View style={[styles.toggleThumb, { transform: [{ translateX: showInAdvance ? 18 : 2 }] }]} />
                </View>
              </TouchableOpacity>
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
            <CalendarPicker selected={selectedDate} onSelect={handleSelectDate} datesSummary={datesSummary} />
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
  primaryButton: { borderRadius: 12, paddingVertical: 14, alignItems: "center", marginBottom: 24 },
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
  fieldLabel: { fontSize: 12, fontWeight: "600", textTransform: "uppercase", letterSpacing: 0.5, marginBottom: 8 },
  dueDateRow: {
    flexDirection: "row", justifyContent: "space-between", alignItems: "center",
    borderRadius: 10, paddingHorizontal: 14, paddingVertical: 12, marginBottom: 12,
  },
  calendarBox: { borderRadius: 12, padding: 12, marginBottom: 12 },
  clearDueBtn: { alignItems: "center", paddingTop: 4 },
  advanceRow: {
    flexDirection: "row", justifyContent: "space-between", alignItems: "center",
    borderRadius: 10, paddingHorizontal: 14, paddingVertical: 12, marginBottom: 12,
  },
  toggle: { width: 42, height: 24, borderRadius: 12, justifyContent: "center" },
  toggleThumb: { width: 20, height: 20, borderRadius: 10, backgroundColor: "#fff" },
  submitButton: { borderRadius: 12, paddingVertical: 14, alignItems: "center", marginBottom: 10 },
  buttonDisabled: { opacity: 0.6 },
  submitText: { color: "#fff", fontSize: 16, fontWeight: "600" },
  cancelButton: { alignItems: "center", paddingVertical: 10 },
  cancelText: { fontSize: 15 },
});
