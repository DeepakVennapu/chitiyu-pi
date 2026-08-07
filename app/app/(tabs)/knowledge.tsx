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
  FlatList,
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

type ViewMode = "entities" | "search";

export default function KnowledgeScreen() {
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
    try {
      // POST /knowledge/facts returns {"result": str} — NL confirmation only.
      await saveFact(factInput.trim());
      setFactInput("");
      setSheetVisible(false);
      loadEntities();
    } finally {
      setSaving(false);
    }
  };

  const entityTypeColor: Record<string, string> = {
    person: "#30D158",
    project: "#007AFF",
    vendor: "#FF9F0A",
    place: "#BF5AF2",
    concept: "#32ADE6",
  };

  return (
    <SafeAreaView style={styles.safe}>
      {/* Search bar */}
      <View style={styles.searchContainer}>
        <TextInput
          style={styles.searchInput}
          value={searchQuery}
          onChangeText={handleSearch}
          placeholder="Search your knowledge…"
          placeholderTextColor="#636366"
          returnKeyType="search"
          clearButtonMode="while-editing"
        />
      </View>

      {/* Save Fact CTA */}
      <TouchableOpacity
        style={styles.saveFact}
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
          {loading && <ActivityIndicator color="#007AFF" style={styles.loader} />}
          {!loading && error && (
            <View style={styles.emptyState}>
              <Text style={styles.errorText}>{error}</Text>
            </View>
          )}
          {!loading && !error && entities.length === 0 && (
            <View style={styles.emptyState}>
              <Text style={styles.emptyText}>No knowledge saved yet.</Text>
              <Text style={styles.emptySubtext}>Use "Save Fact" to start building your knowledge graph.</Text>
            </View>
          )}
          {!error && entities.map((entity) => (
            <View key={entity.id} style={styles.entityRow}>
              <View style={styles.entityInfo}>
                <Text style={styles.entityName}>{entity.name}</Text>
                <View style={[styles.typeBadge, { backgroundColor: (entityTypeColor[entity.type] ?? "#636366") + "33" }]}>
                  <Text style={[styles.typeText, { color: entityTypeColor[entity.type] ?? "#636366" }]}>
                    {entity.type}
                  </Text>
                </View>
              </View>
              {/* fact_count is 0 for MVP — backend GET /knowledge/entities doesn't join facts table yet */}
              {(entity.fact_count ?? 0) > 0 && (
                <Text style={styles.factCount}>
                  {entity.fact_count} {entity.fact_count === 1 ? "fact" : "facts"}
                </Text>
              )}
            </View>
          ))}
        </ScrollView>
      ) : (
        <ScrollView contentContainerStyle={styles.content}>
          {searching && <ActivityIndicator color="#007AFF" style={styles.loader} />}
          {!searching && searchResults.length === 0 && searchQuery.trim() && (
            <View style={styles.emptyState}>
              <Text style={styles.emptyText}>No results for "{searchQuery}"</Text>
            </View>
          )}
          {searchResults.map((fact) => (
            <View key={fact.id} style={styles.factRow}>
              <Text style={styles.factEntity}>{fact.entity_name}</Text>
              <Text style={styles.factContent}>{fact.content}</Text>
              <Text style={styles.factDate}>
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
        onRequestClose={() => setSheetVisible(false)}
      >
        <KeyboardAvoidingView
          behavior={Platform.OS === "ios" ? "padding" : undefined}
          style={styles.modalOverlay}
        >
          <View style={styles.modalSheet}>
            <Text style={styles.modalTitle}>Save a Fact</Text>
            <TextInput
              style={styles.textInput}
              value={factInput}
              onChangeText={setFactInput}
              placeholder="e.g. Mom's birthday is March 15. She lives in Austin."
              placeholderTextColor="#636366"
              multiline
              autoFocus
            />
            <TouchableOpacity
              style={[styles.submitButton, saving && styles.buttonDisabled]}
              onPress={handleSaveFact}
              disabled={saving}
            >
              {saving ? <ActivityIndicator color="#fff" /> : <Text style={styles.submitText}>Save Fact</Text>}
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
  searchContainer: { paddingHorizontal: 16, paddingTop: 12, paddingBottom: 8 },
  searchInput: {
    backgroundColor: "#1C1C1E",
    borderRadius: 10,
    paddingHorizontal: 14,
    paddingVertical: 10,
    color: "#fff",
    fontSize: 15,
  },
  saveFact: {
    marginHorizontal: 16,
    marginBottom: 12,
    backgroundColor: "#007AFF",
    borderRadius: 12,
    paddingVertical: 12,
    alignItems: "center",
  },
  saveFactText: { color: "#fff", fontSize: 15, fontWeight: "600" },
  content: { paddingHorizontal: 16, paddingBottom: 40 },
  loader: { marginTop: 40 },
  emptyState: { paddingTop: 60, alignItems: "center", gap: 8 },
  emptyText: { color: "#fff", fontSize: 15, fontWeight: "600" },
  emptySubtext: { color: "#8E8E93", fontSize: 13, textAlign: "center" },
  errorText: { color: "#FF453A", fontSize: 15, textAlign: "center", padding: 20 },
  entityRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    paddingVertical: 12,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: "#2C2C2E",
  },
  entityInfo: { flexDirection: "row", alignItems: "center", gap: 10, flex: 1 },
  entityName: { color: "#fff", fontSize: 15, fontWeight: "500" },
  typeBadge: { borderRadius: 6, paddingHorizontal: 6, paddingVertical: 2 },
  typeText: { fontSize: 11, fontWeight: "600", textTransform: "uppercase" },
  factCount: { color: "#8E8E93", fontSize: 13 },
  factRow: {
    backgroundColor: "#1C1C1E",
    borderRadius: 10,
    padding: 14,
    marginBottom: 10,
  },
  factEntity: { color: "#007AFF", fontSize: 12, fontWeight: "600", marginBottom: 4 },
  factContent: { color: "#EBEBF5CC", fontSize: 14, lineHeight: 20 },
  factDate: { color: "#636366", fontSize: 11, marginTop: 6 },
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
