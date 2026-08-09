import React, { useState, useEffect, useCallback } from "react";
import {
  View, Text, ScrollView, TouchableOpacity, Modal,
  ActivityIndicator, RefreshControl, StyleSheet, SafeAreaView,
} from "react-native";
import { InsightCard } from "../../components/InsightCard";
import { getInsightsLatest, generateInsights, type InsightCard as InsightCardData } from "../../lib/api";
import { useTheme } from "../../lib/theme";

type Scope = "today" | "week";

export default function InsightsScreen() {
  const { colors } = useTheme();
  const [insights, setInsights] = useState<InsightCardData[]>([]);
  const [dismissed, setDismissed] = useState<Set<number>>(new Set());
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [modalVisible, setModalVisible] = useState(false);
  const [modalScope, setModalScope] = useState<Scope>("today");
  const [activeScope, setActiveScope] = useState<Scope>("today");
  const [error, setError] = useState<string | null>(null);

  const loadInsights = useCallback(async (resetDismissed = false) => {
    setError(null);
    try {
      const data = await getInsightsLatest(activeScope);
      setInsights(data.cards);
      if (resetDismissed) setDismissed(new Set());
    } catch (e) {
      if (e instanceof Error && e.message.includes("404")) {
        setInsights([]);
      } else {
        setError(e instanceof Error ? e.message : "Failed to load insights");
      }
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [activeScope]);

  useEffect(() => { loadInsights(); }, [loadInsights]);

  const handleDismiss = (i: number) =>
    setDismissed((prev) => new Set([...prev, i]));

  const handleGenerate = async () => {
    setGenerating(true);
    setModalVisible(false);
    setActiveScope(modalScope);
    try {
      await generateInsights(modalScope);
      let data = null;
      for (let attempt = 0; attempt < 10; attempt++) {
        await new Promise((r) => setTimeout(r, 2000));
        try {
          data = await getInsightsLatest(modalScope);
          if (data.cards.length > 0) break;
        } catch { /* 404 = not ready */ }
      }
      if (data) { setInsights(data.cards); setDismissed(new Set()); } // intentionally reset on new generation
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to generate insights");
    } finally {
      setGenerating(false);
    }
  };

  const today = new Date().toLocaleDateString("en-US", { weekday: "long", month: "long", day: "numeric" });
  const visibleInsights = insights
    .map((insight, originalIndex) => ({ insight, originalIndex }))
    .filter(({ originalIndex }) => !dismissed.has(originalIndex));

  const s = makeStyles(colors);

  return (
    <SafeAreaView style={s.safe}>
      <ScrollView
        style={s.scroll}
        contentContainerStyle={s.content}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={() => loadInsights(false)} />}
      >
        <View style={s.header}>
          <View>
            <Text style={s.appName}>Chitiyu</Text>
            <Text style={s.date}>{today}</Text>
          </View>
          <TouchableOpacity style={s.refreshButton} onPress={() => setModalVisible(true)}>
            <Text style={s.refreshText}>↻ Refresh</Text>
          </TouchableOpacity>
        </View>

        <View style={s.scopeRow}>
          {(["today", "week"] as Scope[]).map((sc) => (
            <TouchableOpacity
              key={sc}
              style={[s.scopeButton, activeScope === sc && s.scopeButtonActive]}
              onPress={() => setActiveScope(sc)}
            >
              <Text style={[s.scopeText, activeScope === sc && s.scopeTextActive]}>
                {sc === "today" ? "Today" : "This Week"}
              </Text>
            </TouchableOpacity>
          ))}
        </View>

        {loading && (
          <View style={s.centerState}>
            <ActivityIndicator color={colors.accent} />
            <Text style={s.stateText}>Loading insights…</Text>
          </View>
        )}
        {generating && (
          <View style={s.centerState}>
            <ActivityIndicator color={colors.accent} />
            <Text style={s.stateText}>Generating insights…</Text>
          </View>
        )}
        {error && !loading && (
          <View style={s.centerState}>
            <Text style={s.errorText}>{error}</Text>
          </View>
        )}
        {!loading && !generating && !error && insights.length === 0 && (
          <View style={s.centerState}>
            <Text style={s.emptyText}>No insights yet.</Text>
            <Text style={s.emptySubtext}>Log a meal or expense to get started.</Text>
          </View>
        )}
        {!loading && !generating && !error && insights.length > 0 && visibleInsights.length === 0 && (
          <View style={s.centerState}>
            <Text style={s.emptyText}>All caught up.</Text>
            <Text style={s.emptySubtext}>Pull down to refresh or generate new insights.</Text>
          </View>
        )}
        {!loading && !generating && visibleInsights.map(({ insight, originalIndex }) => (
          <InsightCard key={originalIndex} insight={insight} index={originalIndex} onDismiss={handleDismiss} />
        ))}
      </ScrollView>

      <Modal visible={modalVisible} transparent animationType="slide" onRequestClose={() => setModalVisible(false)}>
        <View style={s.modalOverlay}>
          <View style={s.modalSheet}>
            <Text style={s.modalTitle}>Generate Insights</Text>
            <View style={s.scopeRow}>
              {(["today", "week"] as Scope[]).map((sc) => (
                <TouchableOpacity
                  key={sc}
                  style={[s.scopeButton, modalScope === sc && s.scopeButtonActive]}
                  onPress={() => setModalScope(sc)}
                >
                  <Text style={[s.scopeText, modalScope === sc && s.scopeTextActive]}>
                    {sc === "today" ? "Today" : "This Week"}
                  </Text>
                </TouchableOpacity>
              ))}
            </View>
            <TouchableOpacity style={s.generateButton} onPress={handleGenerate}>
              <Text style={s.generateText}>Generate</Text>
            </TouchableOpacity>
            <TouchableOpacity style={s.cancelButton} onPress={() => setModalVisible(false)}>
              <Text style={s.cancelText}>Cancel</Text>
            </TouchableOpacity>
          </View>
        </View>
      </Modal>
    </SafeAreaView>
  );
}

function makeStyles(colors: ReturnType<typeof import("../../lib/theme").useTheme>["colors"]) {
  return StyleSheet.create({
    safe: { flex: 1, backgroundColor: colors.background },
    scroll: { flex: 1 },
    content: { padding: 16, paddingBottom: 32 },
    header: { flexDirection: "row", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 20 },
    appName: { color: colors.text, fontSize: 26, fontWeight: "700", letterSpacing: -0.5 },
    date: { color: colors.textSecondary, fontSize: 13, marginTop: 2 },
    refreshButton: { backgroundColor: colors.card, paddingHorizontal: 12, paddingVertical: 7, borderRadius: 8, marginTop: 4 },
    refreshText: { color: colors.accent, fontSize: 14, fontWeight: "500" },
    centerState: { alignItems: "center", paddingVertical: 60, gap: 8 },
    stateText: { color: colors.textSecondary, fontSize: 14, marginTop: 8 },
    errorText: { color: colors.accentRed, fontSize: 14, textAlign: "center" },
    emptyText: { color: colors.text, fontSize: 16, fontWeight: "600" },
    emptySubtext: { color: colors.textSecondary, fontSize: 14, textAlign: "center" },
    modalOverlay: { flex: 1, backgroundColor: "#00000088", justifyContent: "flex-end" },
    modalSheet: { backgroundColor: colors.card, borderTopLeftRadius: 20, borderTopRightRadius: 20, padding: 24, paddingBottom: 40 },
    modalTitle: { color: colors.text, fontSize: 17, fontWeight: "600", textAlign: "center", marginBottom: 20 },
    scopeRow: { flexDirection: "row", gap: 12, marginBottom: 20 },
    scopeButton: { flex: 1, backgroundColor: colors.cardElevated, borderRadius: 10, paddingVertical: 12, alignItems: "center" },
    scopeButtonActive: { backgroundColor: colors.accent },
    scopeText: { color: colors.textSecondary, fontWeight: "500" },
    scopeTextActive: { color: "#fff" },
    generateButton: { backgroundColor: colors.accent, borderRadius: 12, paddingVertical: 14, alignItems: "center", marginBottom: 10 },
    generateText: { color: "#fff", fontSize: 16, fontWeight: "600" },
    cancelButton: { alignItems: "center", paddingVertical: 10 },
    cancelText: { color: colors.textSecondary, fontSize: 15 },
  });
}
