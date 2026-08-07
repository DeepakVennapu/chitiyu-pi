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
import { ProgressBar } from "../../components/ProgressBar";
import { MacroRings } from "../../components/MacroRings";
import {
  getMealsToday,
  logMeal,
  getHealthMetricsToday,
  type Meal,
  type MealTotals,
  type HealthMetrics,
} from "../../lib/api";
import { TARGETS } from "../../constants/targets";

export default function HealthScreen() {
  const [meals, setMeals] = useState<Meal[]>([]);
  const [totals, setTotals] = useState<MealTotals>({ calories: 0, protein: 0, fat: 0, carbs: 0 });
  const [metrics, setMetrics] = useState<HealthMetrics | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [mealInput, setMealInput] = useState("");
  const [logging, setLogging] = useState(false);
  const [sheetVisible, setSheetVisible] = useState(false);

  const loadData = useCallback(async () => {
    setError(null);
    try {
      const [mealsData, metricsData] = await Promise.all([
        getMealsToday(),
        getHealthMetricsToday(),
      ]);
      setMeals(mealsData.meals);
      setTotals(mealsData.totals);
      setMetrics(metricsData);
    } catch (e: any) {
      setError(e?.message ?? "Failed to load health data");
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => { loadData(); }, [loadData]);

  const handleRefresh = () => { setRefreshing(true); loadData(); };

  const handleLogMeal = async () => {
    if (!mealInput.trim()) return;
    setLogging(true);
    try {
      // POST /health/meals returns {"result": str} — NL confirmation, not a Meal dict.
      // Reload meals+totals from the server to get accurate updated state.
      await logMeal(mealInput.trim());
      setMealInput("");
      setSheetVisible(false);
      await loadData();
    } finally {
      setLogging(false);
    }
  };

  const formatTime = (iso: string) =>
    new Date(iso).toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit" });

  if (loading) {
    return (
      <SafeAreaView style={styles.safe}>
        <View style={styles.center}>
          <ActivityIndicator color="#007AFF" />
        </View>
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
        {/* Calorie progress */}
        <View style={styles.section}>
          <ProgressBar
            label="Calories"
            value={totals.calories}
            target={TARGETS.calories}
            unit=" kcal"
            color="#FF9F0A"
          />
          <ProgressBar
            label="Protein"
            value={totals.protein}
            target={TARGETS.protein}
            unit="g"
            color="#30D158"
          />
          <ProgressBar
            label="Fat"
            value={totals.fat}
            target={TARGETS.fat}
            unit="g"
            color="#FF9F0A"
          />
          <ProgressBar
            label="Carbs"
            value={totals.carbs}
            target={TARGETS.carbs}
            unit="g"
            color="#BF5AF2"
          />
        </View>

        {/* Macro rings */}
        <MacroRings totals={totals} />

        {/* Steps */}
        {metrics?.steps != null && (
          <View style={styles.section}>
            <ProgressBar
              label="Steps"
              value={metrics.steps}
              target={TARGETS.steps}
              unit=""
              color="#32ADE6"
            />
          </View>
        )}

        {/* Sleep summary — only show if at least one metric has data */}
        {metrics && (metrics.sleep_total_mins != null || metrics.sleep_deep_mins != null || metrics.resting_hr != null) && (
          <View style={styles.card}>
            <Text style={styles.sectionTitle}>Last Night</Text>
            <View style={styles.metricsRow}>
              <MetricChip
                label="Deep sleep"
                value={metrics.sleep_deep_mins != null ? `${metrics.sleep_deep_mins}m` : "—"}
                target={`/ ${TARGETS.deepSleepMins}m`}
                ok={metrics.sleep_deep_mins != null ? metrics.sleep_deep_mins >= TARGETS.deepSleepMins : undefined}
              />
              <MetricChip
                label="Total sleep"
                value={metrics.sleep_total_mins != null ? `${Math.round(metrics.sleep_total_mins / 60)}h ${metrics.sleep_total_mins % 60}m` : "—"}
              />
              <MetricChip
                label="Resting HR"
                value={metrics.resting_hr != null ? `${metrics.resting_hr} bpm` : "—"}
              />
            </View>
          </View>
        )}

        {/* Log Meal CTA */}
        <TouchableOpacity
          style={styles.primaryButton}
          onPress={() => setSheetVisible(true)}
        >
          <Text style={styles.primaryButtonText}>+ Log Meal</Text>
        </TouchableOpacity>

        {/* Today's meals */}
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Today's Meals</Text>
          {meals.length === 0 && (
            <Text style={styles.emptyText}>No meals logged yet.</Text>
          )}
          {meals.map((meal) => (
            <View key={meal.id} style={styles.mealRow}>
              <View style={styles.mealInfo}>
                <Text style={styles.mealDesc}>{meal.description}</Text>
                <Text style={styles.mealTime}>{formatTime(meal.logged_at)}</Text>
              </View>
              <Text style={styles.mealKcal}>{meal.calories} kcal</Text>
            </View>
          ))}
        </View>
      </ScrollView>

      {/* Log Meal Sheet */}
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
            <Text style={styles.modalTitle}>Log a Meal</Text>
            <TextInput
              style={styles.textInput}
              value={mealInput}
              onChangeText={setMealInput}
              placeholder="e.g. 2 eggs, turkey bacon, sourdough toast"
              placeholderTextColor="#636366"
              multiline
              autoFocus
            />
            <TouchableOpacity
              style={[styles.generateButton, logging && styles.buttonDisabled]}
              onPress={handleLogMeal}
              disabled={logging}
            >
              {logging ? (
                <ActivityIndicator color="#fff" />
              ) : (
                <Text style={styles.generateText}>Log Meal</Text>
              )}
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

function MetricChip({
  label,
  value,
  target,
  ok,
}: {
  label: string;
  value: string;
  target?: string;
  ok?: boolean;
}) {
  return (
    <View style={chipStyles.chip}>
      <Text style={chipStyles.label}>{label}</Text>
      <Text style={[chipStyles.value, ok === false && chipStyles.warn]}>{value}</Text>
      {target && <Text style={chipStyles.target}>{target}</Text>}
    </View>
  );
}

const chipStyles = StyleSheet.create({
  chip: { alignItems: "center", flex: 1 },
  label: { color: "#8E8E93", fontSize: 11, marginBottom: 3 },
  value: { color: "#fff", fontSize: 15, fontWeight: "600" },
  warn: { color: "#FF453A" },
  target: { color: "#8E8E93", fontSize: 11, marginTop: 1 },
});

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: "#000" },
  scroll: { flex: 1 },
  content: { padding: 16, paddingBottom: 40 },
  center: { flex: 1, alignItems: "center", justifyContent: "center" },
  section: { marginBottom: 20 },
  card: { backgroundColor: "#1C1C1E", borderRadius: 12, padding: 16, marginBottom: 20 },
  sectionTitle: { color: "#fff", fontSize: 15, fontWeight: "600", marginBottom: 12 },
  metricsRow: { flexDirection: "row", justifyContent: "space-around" },
  primaryButton: {
    backgroundColor: "#007AFF",
    borderRadius: 12,
    paddingVertical: 14,
    alignItems: "center",
    marginBottom: 24,
  },
  primaryButtonText: { color: "#fff", fontSize: 16, fontWeight: "600" },
  mealRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    paddingVertical: 10,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: "#2C2C2E",
  },
  mealInfo: { flex: 1, marginRight: 12 },
  mealDesc: { color: "#fff", fontSize: 14 },
  mealTime: { color: "#8E8E93", fontSize: 12, marginTop: 2 },
  mealKcal: { color: "#FF9F0A", fontSize: 14, fontWeight: "600" },
  emptyText: { color: "#8E8E93", fontSize: 14 },
  errorText: { color: "#FF453A", fontSize: 15, textAlign: "center", padding: 20 },
  // Modal
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
    minHeight: 80,
    textAlignVertical: "top",
    marginBottom: 16,
  },
  generateButton: {
    backgroundColor: "#007AFF",
    borderRadius: 12,
    paddingVertical: 14,
    alignItems: "center",
    marginBottom: 10,
  },
  buttonDisabled: { opacity: 0.6 },
  generateText: { color: "#fff", fontSize: 16, fontWeight: "600" },
  cancelButton: { alignItems: "center", paddingVertical: 10 },
  cancelText: { color: "#8E8E93", fontSize: 15 },
});
