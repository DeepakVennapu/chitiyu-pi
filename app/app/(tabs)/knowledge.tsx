import React, { useState, useEffect, useCallback, useRef } from "react";
import {
  View,
  Text,
  ScrollView,
  TextInput,
  TouchableOpacity,
  Modal,
  ActivityIndicator,
  RefreshControl,
  StyleSheet,
  SafeAreaView,
  KeyboardAvoidingView,
  Platform,
} from "react-native";
import {
  searchKnowledge,
  saveFact,
  getEntities,
  type KnowledgeEntity,
  type KnowledgeFact,
} from "../../lib/api";
import { useTheme } from "../../lib/theme";

type ViewMode = "entities" | "search";

export default function KnowledgeScreen() {
  const { colors } = useTheme();
  const [mode, setMode] = useState<ViewMode>("entities");
  const [entities, setEntities] = useState<KnowledgeEntity[]>([]);
  const [searchQuery, setSearchQuery] = useState("");
  const [searchResults, setSearchResults] = useState<KnowledgeFact[]>([]);
  const [searching, setSearching] = useState(false);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [sheetVisible, setSheetVisible] = useState(false);
  const [factInput, setFactInput] = useState("");
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);

  const loadEntities = useCallback(async () => {
    setError(null);
    try {
      // GET /knowledge/entities returns plain KnowledgeEntity[] (no wrapper)
      const data = await getEntities();
      setEntities(data.map((e) => ({ ...e, fact_count: e.fact_count ?? 0 })));
    } catch (e: any) {
      setError(e?.message ?? "Failed to load knowledge");
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => { loadEntities(); }, [loadEntities]);

  const handleRefresh = () => { setRefreshing(true); loadEntities(); };

  const searchTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const handleSearch = useCallback((q: string) => {
    setSearchQuery(q);
    if (!q.trim()) {
      setMode("entities");
      setSearchResults([]);
      return;
    }
    setMode("search");
    if (searchTimer.current) clearTimeout(searchTimer.current);
    searchTimer.current = setTimeout(async () => {
      setSearching(true);
      try {
        const results = await searchKnowledge(q);
        setSearchResults(results);
      } finally {
        setSearching(false);
      }
    }, 400);
  }, []);

  const handleSaveFact = async () => {
    if (!factInput.trim()) return;
    setSaving(true);
    setSaveError(null);
    try {
      // POST /knowledge/facts returns {"result": str} — NL confirmation only.
      await saveFact(factInput.trim());
      setFactInput("");
      setSheetVisible(false);
      loadEntities();
    } catch (e: any) {
      setSaveError(e?.message ?? "Failed to save fact. Check backend connection.");
    } finally {
      setSaving(false);
    }
  };

  const entityTypeColor: Record<string, string> = {
    person: colors.accentGreen,
    project: colors.accent,
    vendor: colors.accentOrange,
    place: colors.accentPurple,
    concept: "#32ADE6",
  };

  return (
    <SafeAreaView style={[styles.safe, { backgroundColor: colors.background }]}>
      {/* Search bar */}
      <View style={styles.searchContainer}>
        <TextInput
          style={[styles.searchInput, { backgroundColor: colors.card, color: colors.text }]}
          value={searchQuery}
          onChangeText={handleSearch}
          placeholder="Search your knowledge…"
          placeholderTextColor={colors.textTertiary}
          returnKeyType="search"
          clearButtonMode="while-editing"
        />
      </View>

      {/* Save Fact CTA */}
      <TouchableOpacity
        style={[styles.saveFact, { backgroundColor: colors.accent }]}
        onPress={() => setSheetVisible(true)}
      >
        <Text style={styles.saveFactText}>+ Save Fact</Text>
      </TouchableOpacity>

      {/* Content */}
      {mode === "entities" ? (
        <ScrollView
          contentContainerStyle={styles.content}
          refreshControl={<RefreshControl refreshing={refreshing} onRefresh={handleRefresh} />}
        >
          {loading && <ActivityIndicator color={colors.accent} style={styles.loader} />}
          {!loading && error && (
            <View style={styles.emptyState}>
              <Text style={{ color: colors.accentRed, fontSize: 15, textAlign: "center", padding: 20 }}>{error}</Text>
            </View>
          )}
          {!loading && !error && entities.length === 0 && (
            <View style={styles.emptyState}>
              <Text style={[styles.emptyText, { color: colors.text }]}>No knowledge saved yet.</Text>
              <Text style={[styles.emptySubtext, { color: colors.textSecondary }]}>Use "Save Fact" to start building your knowledge graph.</Text>
            </View>
          )}
          {!error && entities.map((entity) => (
            <View key={entity.id} style={[styles.entityRow, { borderBottomColor: colors.border }]}>
              <View style={styles.entityInfo}>
                <Text style={[styles.entityName, { color: colors.text }]}>{entity.name}</Text>
                <View style={[styles.typeBadge, { backgroundColor: (entityTypeColor[entity.type] ?? colors.textTertiary) + "33" }]}>
                  <Text style={[styles.typeText, { color: entityTypeColor[entity.type] ?? colors.textTertiary }]}>
                    {entity.type}
                  </Text>
                </View>
              </View>
              {(entity.fact_count ?? 0) > 0 && (
                <Text style={[styles.factCount, { color: colors.textSecondary }]}>
                  {entity.fact_count} {entity.fact_count === 1 ? "fact" : "facts"}
                </Text>
              )}
            </View>
          ))}
        </ScrollView>
      ) : (
        <ScrollView contentContainerStyle={styles.content}>
          {searching && <ActivityIndicator color={colors.accent} style={styles.loader} />}
          {!searching && searchResults.length === 0 && searchQuery.trim() && (
            <View style={styles.emptyState}>
              <Text style={[styles.emptyText, { color: colors.text }]}>No results for "{searchQuery}"</Text>
            </View>
          )}
          {searchResults.map((fact) => (
            <View key={fact.id} style={[styles.factRow, { backgroundColor: colors.card }]}>
              <Text style={[styles.factEntity, { color: colors.accent }]}>{fact.entity_name}</Text>
              <Text style={[styles.factContent, { color: colors.textSecondary }]}>{fact.content}</Text>
              <Text style={[styles.factDate, { color: colors.textTertiary }]}>
                {new Date(fact.created_at).toLocaleDateString("en-US", {
                  month: "short",
                  day: "numeric",
                  year: "numeric",
                })}
              </Text>
            </View>
          ))}
        </ScrollView>
      )}

      {/* Save Fact Sheet */}
      <Modal
        visible={sheetVisible}
        transparent
        animationType="slide"
        onRequestClose={() => { setSheetVisible(false); setSaveError(null); }}
      >
        <KeyboardAvoidingView
          behavior={Platform.OS === "ios" ? "padding" : undefined}
          style={styles.modalOverlay}
        >
          <View style={[styles.modalSheet, { backgroundColor: colors.card }]}>
            <Text style={[styles.modalTitle, { color: colors.text }]}>Save a Fact</Text>
            {saveError && (
              <Text style={[styles.errorText, { color: colors.accentRed }]}>{saveError}</Text>
            )}
            <TextInput
              style={[styles.textInput, { backgroundColor: colors.inputBg, color: colors.text }]}
              value={factInput}
              onChangeText={(t) => { setFactInput(t); setSaveError(null); }}
              placeholder="e.g. Mom's birthday is March 15. She lives in Austin."
              placeholderTextColor={colors.textTertiary}
              multiline
              autoFocus
            />
            <TouchableOpacity
              style={[styles.submitButton, { backgroundColor: colors.accent }, saving && styles.buttonDisabled]}
              onPress={handleSaveFact}
              disabled={saving}
            >
              {saving ? <ActivityIndicator color="#fff" /> : <Text style={styles.submitText}>Save Fact</Text>}
            </TouchableOpacity>
            <TouchableOpacity style={styles.cancelButton} onPress={() => { setSheetVisible(false); setSaveError(null); }}>
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
  searchContainer: { paddingHorizontal: 16, paddingTop: 12, paddingBottom: 8 },
  searchInput: {
    borderRadius: 10,
    paddingHorizontal: 14,
    paddingVertical: 10,
    fontSize: 15,
  },
  saveFact: {
    marginHorizontal: 16,
    marginBottom: 12,
    borderRadius: 12,
    paddingVertical: 12,
    alignItems: "center",
  },
  saveFactText: { color: "#fff", fontSize: 15, fontWeight: "600" },
  content: { paddingHorizontal: 16, paddingBottom: 40 },
  loader: { marginTop: 40 },
  emptyState: { paddingTop: 60, alignItems: "center", gap: 8 },
  emptyText: { fontSize: 15, fontWeight: "600" },
  emptySubtext: { fontSize: 13, textAlign: "center" },
  entityRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    paddingVertical: 12,
    borderBottomWidth: StyleSheet.hairlineWidth,
  },
  entityInfo: { flexDirection: "row", alignItems: "center", gap: 10, flex: 1 },
  entityName: { fontSize: 15, fontWeight: "500" },
  typeBadge: { borderRadius: 6, paddingHorizontal: 6, paddingVertical: 2 },
  typeText: { fontSize: 11, fontWeight: "600", textTransform: "uppercase" },
  factCount: { fontSize: 13 },
  factRow: {
    borderRadius: 10,
    padding: 14,
    marginBottom: 10,
  },
  factEntity: { fontSize: 12, fontWeight: "600", marginBottom: 4 },
  factContent: { fontSize: 14, lineHeight: 20 },
  factDate: { fontSize: 11, marginTop: 6 },
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
    minHeight: 80,
    textAlignVertical: "top",
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
  errorText: { fontSize: 13, marginBottom: 10, textAlign: "center" },
});
