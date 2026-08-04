import React, { useState, useEffect, useCallback } from "react";
import {
  View,
  Text,
  ScrollView,
  TouchableOpacity,
  Modal,
  ActivityIndicator,
  RefreshControl,
  StyleSheet,
  SafeAreaView,
} from "react-native";
import { InsightCard } from "../../components/InsightCard";
import {
  getInsightsLatest,
  generateInsights,
  type InsightCard as InsightCardData,
} from "../../lib/api";

type Scope = "today" | "week";

export default function InsightsScreen() {
  const [insights, setInsights] = useState<InsightCardData[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [modalVisible, setModalVisible] = useState(false);
  const [modalScope, setModalScope] = useState<Scope>("today");
  const [activeScope, setActiveScope] = useState<Scope>("today");
  const [error, setError] = useState<string | null>(null);

  const loadInsights = useCallback(async () => {
    setError(null);
    try {
      const data = await getInsightsLatest(activeScope);
      setInsights(data.cards);  // backend returns `cards`, not `insights`
    } catch (e) {
      // 404 means no insights generated yet — show empty state, not an error
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

  useEffect(() => {
    loadInsights();
  }, [loadInsights]);

  const handleGenerate = async () => {
    setGenerating(true);
    setModalVisible(false);
    setActiveScope(modalScope);
    try {
      // POST /insights/generate returns {status, scope} — NOT cards.
      // Fire the trigger then poll latest to get the fresh cards.
      await generateInsights(modalScope);
      // Brief delay to allow background generation to complete
      await new Promise((r) => setTimeout(r, 3000));
      const data = await getInsightsLatest(modalScope);
      setInsights(data.cards);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to generate insights");
    } finally {
      setGenerating(false);
    }
  };

  const today = new Date().toLocaleDateString("en-US", {
    weekday: "long",
    month: "long",
    day: "numeric",
  });

  return (
    <SafeAreaView style={styles.safe}>
      <ScrollView
        style={styles.scroll}
        contentContainerStyle={styles.content}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={loadInsights} />}
      >
        {/* Header */}
        <View style={styles.header}>
          <View>
            <Text style={styles.appName}>Chitiyu</Text>
            <Text style={styles.date}>{today}</Text>
          </View>
          <TouchableOpacity
            style={styles.refreshButton}
            onPress={() => setModalVisible(true)}
          >
            <Text style={styles.refreshText}>↻ Refresh</Text>
          </TouchableOpacity>
        </View>

        {/* Scope segmented control */}
        <View style={styles.scopeRow}>
          {(["today", "week"] as Scope[]).map((s) => (
            <TouchableOpacity
              key={s}
              style={[styles.scopeButton, activeScope === s && styles.scopeButtonActive]}
              onPress={() => setActiveScope(s)}
            >
              <Text style={[styles.scopeText, activeScope === s && styles.scopeTextActive]}>
                {s === "today" ? "Today" : "This Week"}
              </Text>
            </TouchableOpacity>
          ))}
        </View>

        {/* States */}
        {loading && (
          <View style={styles.centerState}>
            <ActivityIndicator color="#007AFF" />
            <Text style={styles.stateText}>Loading insights…</Text>
          </View>
        )}

        {generating && (
          <View style={styles.centerState}>
            <ActivityIndicator color="#007AFF" />
            <Text style={styles.stateText}>Generating insights…</Text>
          </View>
        )}

        {error && !loading && (
          <View style={styles.centerState}>
            <Text style={styles.errorText}>{error}</Text>
          </View>
        )}

        {!loading && !generating && !error && insights.length === 0 && (
          <View style={styles.centerState}>
            <Text style={styles.emptyText}>No insights yet.</Text>
            <Text style={styles.emptySubtext}>
              Log a meal or expense to get started.
            </Text>
          </View>
        )}

        {!loading && !generating && insights.map((insight, i) => (
          <InsightCard key={i} insight={insight} />
        ))}
      </ScrollView>

      {/* Refresh Modal */}
      <Modal
        visible={modalVisible}
        transparent
        animationType="slide"
        onRequestClose={() => setModalVisible(false)}
      >
        <View style={styles.modalOverlay}>
          <View style={styles.modalSheet}>
            <Text style={styles.modalTitle}>Generate Insights</Text>

            <View style={styles.scopeRow}>
              {(["today", "week"] as Scope[]).map((s) => (
                <TouchableOpacity
                  key={s}
                  style={[styles.scopeButton, modalScope === s && styles.scopeButtonActive]}
                  onPress={() => setModalScope(s)}
                >
                  <Text
                    style={[styles.scopeText, modalScope === s && styles.scopeTextActive]}
                  >
                    {s === "today" ? "Today" : "This Week"}
                  </Text>
                </TouchableOpacity>
              ))}
            </View>

            <TouchableOpacity style={styles.generateButton} onPress={handleGenerate}>
              <Text style={styles.generateText}>Generate</Text>
            </TouchableOpacity>

            <TouchableOpacity
              style={styles.cancelButton}
              onPress={() => setModalVisible(false)}
            >
              <Text style={styles.cancelText}>Cancel</Text>
            </TouchableOpacity>
          </View>
        </View>
      </Modal>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: "#000" },
  scroll: { flex: 1 },
  content: { padding: 16, paddingBottom: 32 },
  header: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "flex-start",
    marginBottom: 20,
  },
  appName: { color: "#fff", fontSize: 24, fontWeight: "700" },
  date: { color: "#8E8E93", fontSize: 13, marginTop: 2 },
  refreshButton: {
    backgroundColor: "#1C1C1E",
    paddingHorizontal: 12,
    paddingVertical: 7,
    borderRadius: 8,
    marginTop: 4,
  },
  refreshText: { color: "#007AFF", fontSize: 14, fontWeight: "500" },
  centerState: { alignItems: "center", paddingVertical: 60, gap: 8 },
  stateText: { color: "#8E8E93", fontSize: 14, marginTop: 8 },
  errorText: { color: "#FF453A", fontSize: 14, textAlign: "center" },
  emptyText: { color: "#fff", fontSize: 16, fontWeight: "600" },
  emptySubtext: { color: "#8E8E93", fontSize: 14, textAlign: "center" },
  // Modal
  modalOverlay: { flex: 1, backgroundColor: "#00000088", justifyContent: "flex-end" },
  modalSheet: {
    backgroundColor: "#1C1C1E",
    borderTopLeftRadius: 20,
    borderTopRightRadius: 20,
    padding: 24,
    paddingBottom: 40,
  },
  modalTitle: {
    color: "#fff",
    fontSize: 17,
    fontWeight: "600",
    textAlign: "center",
    marginBottom: 20,
  },
  scopeRow: { flexDirection: "row", gap: 12, marginBottom: 20 },
  scopeButton: {
    flex: 1,
    backgroundColor: "#2C2C2E",
    borderRadius: 10,
    paddingVertical: 12,
    alignItems: "center",
  },
  scopeButtonActive: { backgroundColor: "#007AFF" },
  scopeText: { color: "#8E8E93", fontWeight: "500" },
  scopeTextActive: { color: "#fff" },
  generateButton: {
    backgroundColor: "#007AFF",
    borderRadius: 12,
    paddingVertical: 14,
    alignItems: "center",
    marginBottom: 10,
  },
  generateText: { color: "#fff", fontSize: 16, fontWeight: "600" },
  cancelButton: { alignItems: "center", paddingVertical: 10 },
  cancelText: { color: "#8E8E93", fontSize: 15 },
});
