import React, { useState, useEffect, useCallback } from "react";
import { SmartInputSheet } from "../../components/SmartInputSheet";
import {
  View, Text, ScrollView, TouchableOpacity, Modal, TextInput,
  ActivityIndicator, RefreshControl, StyleSheet, SafeAreaView,
  KeyboardAvoidingView, Platform, FlatList,
} from "react-native";
import { ProgressBar } from "../../components/ProgressBar";
import { MacroRings } from "../../components/MacroRings";
import { MealRow } from "../../components/MealRow";
import {
  getMealsToday, getMealsForDate, logMeal, getMealPreview,
  logMealFromRecipe, logMealParsed, getRecipes, createRecipe, deleteMeal,
  type Meal, type MealTotals, type HealthMetrics, type MealPreviewResult, type Recipe,
} from "../../lib/api";
import { TARGETS } from "../../constants/targets";
import { useTheme, type Colors } from "../../lib/theme";
import { parseLocalTs, nowISO, todayLocal, dateToLocal } from "../../lib/dateUtils";

type MealSection = { label: string; meals: Meal[] };
type LogTab = "describe" | "recipes";
type MealTime = "breakfast" | "lunch" | "dinner";

function defaultMealTime(): MealTime {
  const h = new Date().getHours();
  if (h < 12) return "breakfast";
  if (h < 18) return "lunch";
  return "dinner";
}

// SQLite stores logged_at as "YYYY-MM-DD HH:MM:SS" in local time.
// parseLocalTs (from dateUtils) handles bare strings correctly — no Z appended.

function bucketMeals(meals: Meal[]): MealSection[] {
  const sections: { label: string; hours: [number, number] }[] = [
    { label: "Breakfast", hours: [0, 12] },
    { label: "Lunch", hours: [12, 18] },
    { label: "Dinner", hours: [18, 24] },
  ];
  return sections
    .map(({ label, hours: [start, end] }) => ({
      label,
      meals: meals.filter((m) => {
        const d = parseLocalTs(m.logged_at);
        if (!d) return false;
        const hour = d.getHours();
        return hour >= start && hour < end;
      }),
    }))
    .filter((s) => s.meals.length > 0);
}

export default function HealthScreen() {
  const { colors } = useTheme();
  const [selectedDate, setSelectedDate] = useState(todayLocal());
  const [meals, setMeals] = useState<Meal[]>([]);
  const [totals, setTotals] = useState<MealTotals>({ calories: 0, protein: 0, fat: 0, carbs: 0 });
  const [metrics, setMetrics] = useState<HealthMetrics | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // SmartInputSheet state
  const [smartOpen, setSmartOpen] = useState(false);

  // Sheet state
  const [sheetVisible, setSheetVisible] = useState(false);
  const [logTab, setLogTab] = useState<LogTab>("describe");
  const [mealInput, setMealInput] = useState("");

  // Preview/confirm flow
  const [previewing, setPreviewing] = useState(false);
  const [preview, setPreview] = useState<MealPreviewResult | null>(null);
  const [confirmedPreview, setConfirmedPreview] = useState<MealPreviewResult | null>(null);
  const [logging, setLogging] = useState(false);
  const [mealTime, setMealTime] = useState<"breakfast" | "lunch" | "dinner">(defaultMealTime());

  // Recipe state
  const [recipes, setRecipes] = useState<Recipe[]>([]);
  const [recipesLoading, setRecipesLoading] = useState(false);
  const [savingRecipe, setSavingRecipe] = useState(false);
  const [showSaveRecipe, setShowSaveRecipe] = useState(false);
  const [recipeName, setRecipeName] = useState("");

  const loadData = useCallback(async (date: string) => {
    setError(null);
    try {
      const mealsData = date === todayLocal()
        ? await getMealsToday()
        : await getMealsForDate(date);
      setMeals(mealsData.meals);
      setMetrics(mealsData.metrics);
      // Backend does not return totals — sum client-side
      const computed: MealTotals = mealsData.meals.reduce(
        (acc, m) => ({
          calories: acc.calories + (m.calories ?? 0),
          protein: acc.protein + (m.protein ?? 0),
          fat: acc.fat + (m.fat ?? 0),
          carbs: acc.carbs + (m.carbs ?? 0),
        }),
        { calories: 0, protein: 0, fat: 0, carbs: 0 }
      );
      setTotals(computed);
    } catch (e: any) {
      setError(e?.message ?? "Failed to load health data");
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  const loadRecipes = useCallback(async () => {
    setRecipesLoading(true);
    try {
      const data = await getRecipes();
      setRecipes(data);
    } finally {
      setRecipesLoading(false);
    }
  }, []);

  useEffect(() => { loadData(selectedDate); }, [selectedDate]);

  const handleRefresh = () => { setRefreshing(true); loadData(selectedDate); };

  const handlePrevDay = () => {
    const d = new Date(selectedDate + "T12:00:00");
    d.setDate(d.getDate() - 1);
    setSelectedDate(dateToLocal(d));
  };

  const handleNextDay = () => {
    const next = new Date(selectedDate + "T12:00:00");
    next.setDate(next.getDate() + 1);
    const nextStr = dateToLocal(next);
    if (nextStr <= todayLocal()) setSelectedDate(nextStr);
  };

  const isToday = selectedDate === todayLocal();

  const dateLabel = (() => {
    if (isToday) return "Today";
    const yesterday = new Date();
    yesterday.setDate(yesterday.getDate() - 1);
    if (selectedDate === dateToLocal(yesterday)) return "Yesterday";
    const d = new Date(selectedDate + "T12:00:00");
    return d.toLocaleDateString("en-US", { month: "short", day: "numeric" });
  })();

  const openSheet = () => {
    setPreview(null);
    setConfirmedPreview(null);
    setMealInput("");
    setLogTab("describe");
    setShowSaveRecipe(false);
    setRecipes([]);
    setMealTime(defaultMealTime());
    setSheetVisible(true);
  };

  const handleSwitchToRecipes = () => {
    setLogTab("recipes");
    loadRecipes();
  };

  const handlePreview = async () => {
    if (!mealInput.trim()) return;
    setPreviewing(true);
    try {
      const result = await getMealPreview(mealInput.trim());
      setPreview(result);
      setRecipeName(result.description);
    } finally {
      setPreviewing(false);
    }
  };

  const handleConfirmLog = async () => {
    if (!preview) return;
    setConfirmedPreview(preview);
    setLogging(true);
    try {
      await logMealParsed(preview, nowISO());
      setSheetVisible(false);
      setPreview(null);
      setMealInput("");
      await loadData(selectedDate);
      // Ask to save as recipe
      setShowSaveRecipe(true);
    } finally {
      setLogging(false);
    }
  };

  const handleSaveAsRecipe = async () => {
    if (!confirmedPreview || !recipeName.trim()) return;
    setSavingRecipe(true);
    try {
      await createRecipe(
        recipeName.trim(), confirmedPreview.calories, confirmedPreview.protein,
        confirmedPreview.fat ?? undefined, confirmedPreview.carbs ?? undefined
      );
      await loadRecipes();
    } finally {
      setSavingRecipe(false);
      setShowSaveRecipe(false);
      setConfirmedPreview(null);
      setRecipeName("");
    }
  };

  const handleLogFromRecipe = async (recipeId: number) => {
    setLogging(true);
    try {
      await logMealFromRecipe(recipeId);
      setSheetVisible(false);
      await loadData(selectedDate);
    } finally {
      setLogging(false);
    }
  };

  const handleDeleteMeal = async (id: number) => {
    await deleteMeal(id);
    const remaining = meals.filter((m) => m.id !== id);
    setMeals(remaining);
    const computed: MealTotals = remaining.reduce(
      (acc, m) => ({
        calories: acc.calories + (m.calories ?? 0),
        protein: acc.protein + (m.protein ?? 0),
        fat: acc.fat + (m.fat ?? 0),
        carbs: acc.carbs + (m.carbs ?? 0),
      }),
      { calories: 0, protein: 0, fat: 0, carbs: 0 }
    );
    setTotals(computed);
  };

  const mealSections = bucketMeals(meals);

  if (loading) {
    return (
      <SafeAreaView style={{ flex: 1, backgroundColor: colors.background }}>
        <View style={styles.center}><ActivityIndicator color={colors.accent} /></View>
      </SafeAreaView>
    );
  }

  if (error) {
    return (
      <SafeAreaView style={{ flex: 1, backgroundColor: colors.background }}>
        <View style={styles.center}>
          <Text style={{ color: colors.accentRed, fontSize: 15, textAlign: "center", padding: 20 }}>{error}</Text>
        </View>
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: colors.background }}>
      <ScrollView
        style={{ flex: 1 }}
        contentContainerStyle={styles.content}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={handleRefresh} />}
      >
        {/* Date nav */}
        <View style={[styles.dateNav, styles.px]}>
          <TouchableOpacity onPress={handlePrevDay} style={styles.dateArrow}>
            <Text style={[styles.dateArrowText, { color: colors.text }]}>‹</Text>
          </TouchableOpacity>
          <Text style={[styles.dateLabel, { color: colors.text }]}>{dateLabel}</Text>
          <TouchableOpacity onPress={handleNextDay} style={styles.dateArrow} disabled={isToday}>
            <Text style={[styles.dateArrowText, { color: isToday ? colors.textSecondary : colors.text }]}>›</Text>
          </TouchableOpacity>
        </View>

        {/* Macro progress */}
        <View style={[styles.section, styles.px]}>
          <ProgressBar label="Calories" value={totals.calories} target={TARGETS.calories} unit=" kcal" color={colors.accentOrange} />
          <ProgressBar label="Protein" value={totals.protein} target={TARGETS.protein} unit="g" color={colors.accentGreen} />
          <ProgressBar label="Fat" value={totals.fat} target={TARGETS.fat} unit="g" color={colors.accentOrange} />
          <ProgressBar label="Carbs" value={totals.carbs} target={TARGETS.carbs} unit="g" color={colors.accentPurple} />
        </View>

        <MacroRings totals={totals} />

        {metrics?.steps != null && (
          <View style={[styles.section, styles.px]}>
            <ProgressBar label="Steps" value={metrics.steps} target={TARGETS.steps} unit="" color={colors.accent} />
          </View>
        )}

        {metrics && (metrics.sleep_total_mins != null || metrics.sleep_deep_mins != null || metrics.resting_hr != null) && (
          <View style={[styles.card, styles.mx, { backgroundColor: colors.card }]}>
            <Text style={[styles.sectionTitle, { color: colors.text }]}>Last Night</Text>
            <View style={styles.metricsRow}>
              <MetricChip label="Deep sleep" value={metrics.sleep_deep_mins != null ? `${metrics.sleep_deep_mins}m` : "—"} target={`/ ${TARGETS.deepSleepMins}m`} ok={metrics.sleep_deep_mins != null ? metrics.sleep_deep_mins >= TARGETS.deepSleepMins : undefined} colors={colors} />
              <MetricChip label="Total sleep" value={metrics.sleep_total_mins != null ? `${Math.round(metrics.sleep_total_mins / 60)}h ${metrics.sleep_total_mins % 60}m` : "—"} colors={colors} />
              <MetricChip label="Resting HR" value={metrics.resting_hr != null ? `${metrics.resting_hr} bpm` : "—"} colors={colors} />
            </View>
          </View>
        )}

        {/* Log Meal CTA — only on today */}
        {isToday && (
          <TouchableOpacity style={[styles.primaryButton, styles.mx, { backgroundColor: colors.accent }]} onPress={() => setSmartOpen(true)}>
            <Text style={styles.primaryButtonText}>+ Log Meal</Text>
          </TouchableOpacity>
        )}

        {/* Today's meals by section */}
        {meals.length === 0 ? (
          <Text style={[styles.emptyText, styles.px, { color: colors.textSecondary }]}>No meals logged yet.</Text>
        ) : (
          mealSections.map((section) => (
            <View key={section.label} style={styles.section}>
              <Text style={[styles.sectionTitle, styles.px, { color: colors.text }]}>{section.label}</Text>
              {section.meals.map((meal) => (
                <MealRow key={meal.id} meal={meal} onDelete={handleDeleteMeal} />
              ))}
            </View>
          ))
        )}
      </ScrollView>

      {/* Log Meal Sheet */}
      <Modal visible={sheetVisible} transparent animationType="slide" onRequestClose={() => setSheetVisible(false)}>
        <KeyboardAvoidingView behavior={Platform.OS === "ios" ? "padding" : undefined} style={styles.modalOverlay}>
          <View style={[styles.modalSheet, { backgroundColor: colors.card }]}>
            <Text style={[styles.modalTitle, { color: colors.text }]}>Log a Meal</Text>

            {/* Tab switcher */}
            <View style={[styles.tabRow, { backgroundColor: colors.cardElevated }]}>
              <TouchableOpacity
                style={[styles.tabBtn, logTab === "describe" && { backgroundColor: colors.card }]}
                onPress={() => setLogTab("describe")}
              >
                <Text style={[styles.tabText, { color: logTab === "describe" ? colors.text : colors.textSecondary }]}>Describe</Text>
              </TouchableOpacity>
              <TouchableOpacity
                style={[styles.tabBtn, logTab === "recipes" && { backgroundColor: colors.card }]}
                onPress={handleSwitchToRecipes}
              >
                <Text style={[styles.tabText, { color: logTab === "recipes" ? colors.text : colors.textSecondary }]}>Quick Select</Text>
              </TouchableOpacity>
            </View>

            {logTab === "describe" ? (
              <>
                {preview ? (
                  // Confirmation view
                  <View style={styles.previewBox}>
                    <Text style={[styles.previewName, { color: colors.text }]}>{preview.description}</Text>
                    <View style={styles.macroChips}>
                      <MacroChip label="Cal" value={`${preview.calories}`} color={colors.accentOrange} />
                      <MacroChip label="Pro" value={`${preview.protein}g`} color={colors.accentGreen} />
                      {preview.fat != null && <MacroChip label="Fat" value={`${preview.fat}g`} color={colors.accentOrange} />}
                      {preview.carbs != null && <MacroChip label="Carbs" value={`${preview.carbs}g`} color={colors.accentPurple} />}
                    </View>
                    <Text style={[styles.previewQuestion, { color: colors.textSecondary }]}>When did you eat this?</Text>
                    <View style={[styles.timeRow, { backgroundColor: colors.cardElevated }]}>
                      {(["breakfast", "lunch", "dinner"] as MealTime[]).map((slot) => (
                        <TouchableOpacity
                          key={slot}
                          style={[styles.timeBtn, mealTime === slot && { backgroundColor: colors.accent }]}
                          onPress={() => setMealTime(slot)}
                        >
                          <Text style={[styles.timeBtnText, { color: mealTime === slot ? "#fff" : colors.textSecondary }]}>
                            {slot.charAt(0).toUpperCase() + slot.slice(1)}
                          </Text>
                        </TouchableOpacity>
                      ))}
                    </View>
                    <View style={styles.confirmRow}>
                      <TouchableOpacity
                        style={[styles.confirmBtn, { backgroundColor: colors.accentGreen }]}
                        onPress={handleConfirmLog}
                        disabled={logging}
                      >
                        {logging ? <ActivityIndicator color="#fff" /> : <Text style={styles.confirmBtnText}>Log it</Text>}
                      </TouchableOpacity>
                      <TouchableOpacity
                        style={[styles.confirmBtn, { backgroundColor: colors.cardElevated }]}
                        onPress={() => setPreview(null)}
                      >
                        <Text style={[styles.confirmBtnText, { color: colors.text }]}>Edit</Text>
                      </TouchableOpacity>
                    </View>
                  </View>
                ) : (
                  // Input view
                  <>
                    <TextInput
                      style={[styles.textInput, { backgroundColor: colors.inputBg, color: colors.text }]}
                      value={mealInput}
                      onChangeText={setMealInput}
                      placeholder="e.g. 2 eggs, turkey bacon, sourdough toast"
                      placeholderTextColor={colors.textTertiary}
                      multiline
                      autoFocus
                    />
                    <TouchableOpacity
                      style={[styles.generateButton, { backgroundColor: colors.accent }, (previewing || !mealInput.trim()) && styles.buttonDisabled]}
                      onPress={handlePreview}
                      disabled={previewing || !mealInput.trim()}
                    >
                      {previewing ? <ActivityIndicator color="#fff" /> : <Text style={styles.generateText}>Analyze</Text>}
                    </TouchableOpacity>
                  </>
                )}
              </>
            ) : (
              // Recipes tab
              <>
                {recipesLoading ? (
                  <ActivityIndicator color={colors.accent} style={{ marginVertical: 30 }} />
                ) : recipes.length === 0 ? (
                  <View style={styles.emptyState}>
                    <Text style={[styles.emptyStateText, { color: colors.textSecondary }]}>No saved recipes yet.</Text>
                    <Text style={[styles.emptyStateSubtext, { color: colors.textTertiary }]}>Log a meal and save it as a recipe for quick access.</Text>
                  </View>
                ) : (
                  <FlatList
                    data={recipes}
                    keyExtractor={(r) => String(r.id)}
                    style={{ maxHeight: 300 }}
                    renderItem={({ item }) => (
                      <TouchableOpacity
                        style={[styles.recipeRow, { borderBottomColor: colors.border }]}
                        onPress={() => handleLogFromRecipe(item.id)}
                        disabled={logging}
                      >
                        <Text style={[styles.recipeName, { color: colors.text }]}>{item.name}</Text>
                        <Text style={[styles.recipeKcal, { color: colors.accentOrange }]}>{item.calories} kcal</Text>
                      </TouchableOpacity>
                    )}
                  />
                )}
              </>
            )}

            <TouchableOpacity style={styles.cancelButton} onPress={() => setSheetVisible(false)}>
              <Text style={[styles.cancelText, { color: colors.textSecondary }]}>Cancel</Text>
            </TouchableOpacity>
          </View>
        </KeyboardAvoidingView>
      </Modal>

      {/* Save as Recipe prompt — centered, no autoFocus to avoid keyboard covering it */}
      <Modal visible={showSaveRecipe} transparent animationType="fade" onRequestClose={() => setShowSaveRecipe(false)}>
        <View style={styles.recipeModalOverlay}>
          <View style={[styles.recipeModalCard, { backgroundColor: colors.card }]}>
            <Text style={[styles.modalTitle, { color: colors.text }]}>Save as Recipe?</Text>
            <TextInput
              style={[styles.textInput, { backgroundColor: colors.inputBg, color: colors.text, minHeight: 0 }]}
              value={recipeName}
              onChangeText={setRecipeName}
              placeholder="Recipe name"
              placeholderTextColor={colors.textTertiary}
            />
            <View style={styles.confirmRow}>
              <TouchableOpacity
                style={[styles.confirmBtn, { backgroundColor: colors.accent }]}
                onPress={handleSaveAsRecipe}
                disabled={savingRecipe}
              >
                {savingRecipe ? <ActivityIndicator color="#fff" /> : <Text style={styles.confirmBtnText}>Save</Text>}
              </TouchableOpacity>
              <TouchableOpacity
                style={[styles.confirmBtn, { backgroundColor: colors.cardElevated }]}
                onPress={() => setShowSaveRecipe(false)}
              >
                <Text style={[styles.confirmBtnText, { color: colors.text }]}>Skip</Text>
              </TouchableOpacity>
            </View>
          </View>
        </View>
      </Modal>

      <SmartInputSheet
        visible={smartOpen}
        onClose={() => setSmartOpen(false)}
        onConfirmed={() => { setSmartOpen(false); loadData(selectedDate); }}
        domainLock="health"
      />
    </SafeAreaView>
  );
}

function MetricChip({ label, value, target, ok, colors }: {
  label: string; value: string; target?: string; ok?: boolean; colors: Colors;
}) {
  return (
    <View style={chipStyles.chip}>
      <Text style={[chipStyles.label, { color: colors.textSecondary }]}>{label}</Text>
      <Text style={[chipStyles.value, { color: ok === false ? colors.accentRed : colors.text }]}>{value}</Text>
      {target && <Text style={[chipStyles.target, { color: colors.textSecondary }]}>{target}</Text>}
    </View>
  );
}

function MacroChip({ label, value, color }: { label: string; value: string; color: string }) {
  return (
    <View style={[chipStyles.macroChip, { backgroundColor: color + "22" }]}>
      <Text style={[chipStyles.macroLabel, { color }]}>{label}</Text>
      <Text style={[chipStyles.macroValue, { color }]}>{value}</Text>
    </View>
  );
}

const chipStyles = StyleSheet.create({
  chip: { alignItems: "center", flex: 1 },
  label: { fontSize: 11, marginBottom: 3 },
  value: { fontSize: 15, fontWeight: "600" },
  target: { fontSize: 11, marginTop: 1 },
  macroChip: { borderRadius: 8, paddingHorizontal: 10, paddingVertical: 6, alignItems: "center" },
  macroLabel: { fontSize: 10, fontWeight: "600", textTransform: "uppercase" },
  macroValue: { fontSize: 14, fontWeight: "700" },
});

const styles = StyleSheet.create({
  center: { flex: 1, alignItems: "center", justifyContent: "center" },
  content: { paddingTop: 16, paddingBottom: 40 },
  px: { paddingHorizontal: 16 },
  mx: { marginHorizontal: 16 },
  dateNav: { flexDirection: "row", alignItems: "center", justifyContent: "center", marginBottom: 20 },
  dateArrow: { paddingHorizontal: 20, paddingVertical: 4 },
  dateArrowText: { fontSize: 28, fontWeight: "300", lineHeight: 32 },
  dateLabel: { fontSize: 16, fontWeight: "600", minWidth: 100, textAlign: "center" },
  section: { marginBottom: 20 },
  card: { borderRadius: 12, padding: 16, marginBottom: 20 },
  sectionTitle: { fontSize: 15, fontWeight: "600", marginBottom: 8 },
  metricsRow: { flexDirection: "row", justifyContent: "space-around" },
  primaryButton: { borderRadius: 12, paddingVertical: 14, alignItems: "center", marginBottom: 24 },
  primaryButtonText: { color: "#fff", fontSize: 16, fontWeight: "600" },
  emptyText: { fontSize: 14 },
  // Modal
  modalOverlay: { flex: 1, backgroundColor: "#00000088", justifyContent: "flex-end" },
  modalSheet: { borderTopLeftRadius: 20, borderTopRightRadius: 20, padding: 24, paddingBottom: 40 },
  modalTitle: { fontSize: 17, fontWeight: "600", marginBottom: 16 },
  recipeModalOverlay: { flex: 1, backgroundColor: "#00000088", justifyContent: "center", paddingHorizontal: 24 },
  recipeModalCard: { borderRadius: 16, padding: 24 },
  // Meal time picker
  timeRow: { flexDirection: "row", borderRadius: 10, padding: 3, marginBottom: 14 },
  timeBtn: { flex: 1, paddingVertical: 8, alignItems: "center", borderRadius: 8 },
  timeBtnText: { fontSize: 13, fontWeight: "500" },
  tabRow: { flexDirection: "row", borderRadius: 10, padding: 3, marginBottom: 16 },
  tabBtn: { flex: 1, paddingVertical: 8, alignItems: "center", borderRadius: 8 },
  tabText: { fontSize: 14, fontWeight: "500" },
  textInput: { borderRadius: 10, padding: 14, fontSize: 15, minHeight: 80, textAlignVertical: "top", marginBottom: 16 },
  generateButton: { borderRadius: 12, paddingVertical: 14, alignItems: "center", marginBottom: 10 },
  buttonDisabled: { opacity: 0.5 },
  generateText: { color: "#fff", fontSize: 16, fontWeight: "600" },
  cancelButton: { alignItems: "center", paddingVertical: 10 },
  cancelText: { fontSize: 15 },
  // Preview
  previewBox: { marginBottom: 16 },
  previewName: { fontSize: 16, fontWeight: "600", marginBottom: 10 },
  macroChips: { flexDirection: "row", gap: 8, flexWrap: "wrap", marginBottom: 12 },
  previewQuestion: { fontSize: 14, marginBottom: 12 },
  confirmRow: { flexDirection: "row", gap: 10 },
  confirmBtn: { flex: 1, borderRadius: 10, paddingVertical: 12, alignItems: "center" },
  confirmBtnText: { color: "#fff", fontSize: 15, fontWeight: "600" },
  // Recipes
  recipeRow: { flexDirection: "row", justifyContent: "space-between", alignItems: "center", paddingVertical: 12, borderBottomWidth: StyleSheet.hairlineWidth },
  recipeName: { fontSize: 15, fontWeight: "500", flex: 1 },
  recipeKcal: { fontSize: 13, fontWeight: "600" },
  emptyState: { paddingVertical: 30, alignItems: "center", gap: 6 },
  emptyStateText: { fontSize: 15, fontWeight: "600" },
  emptyStateSubtext: { fontSize: 13, textAlign: "center" },
});
