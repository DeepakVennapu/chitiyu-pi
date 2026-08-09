import React, { useState, useRef } from "react";
import {
  Modal, View, Text, TextInput, TouchableOpacity, ScrollView,
  ActivityIndicator, KeyboardAvoidingView, Platform, StyleSheet,
} from "react-native";
import { useTheme } from "../lib/theme";
import {
  chatMessage, confirmDomain, previewDomain,
  type ChatResponse, type DomainBlock, type DomainName, type DomainPreview,
  type HealthPreview, type FinancePreview, type TaskPreviewItem,
} from "../lib/api";

interface SmartInputSheetProps {
  visible: boolean;
  onClose: () => void;
  onConfirmed: () => void;
  domainLock?: DomainName;
  initialText?: string;
}

type Phase =
  | { type: "idle" }
  | { type: "loading" }
  | { type: "error"; message: string }
  | { type: "preview"; response: ChatResponse; domainIndex: number }
  | { type: "confirming"; response: ChatResponse; domainIndex: number }
  | { type: "correcting"; domainIndex: number; prefill: string; response: ChatResponse }
  | { type: "done" };

// ── Sub-cards ────────────────────────────────────────────────────────────────

function HealthPreviewCard({ preview, colors }: { preview: HealthPreview; colors: any }) {
  return (
    <View>
      <Text style={{ color: colors.text, fontWeight: "600", marginBottom: 4 }}>{preview.description}</Text>
      <Text style={{ color: colors.textSecondary }}>{preview.calories} kcal · {preview.protein}g protein</Text>
      {preview.fat != null && (
        <Text style={{ color: colors.textSecondary }}>{preview.fat}g fat · {preview.carbs}g carbs</Text>
      )}
    </View>
  );
}

function FinancePreviewCard({ preview, colors }: { preview: FinancePreview; colors: any }) {
  const sign = preview.amount < 0 ? "-" : "+";
  return (
    <View>
      <Text style={{ color: colors.text, fontWeight: "600", marginBottom: 4 }}>{preview.description}</Text>
      <Text style={{ color: colors.textSecondary }}>
        {sign}${Math.abs(preview.amount).toFixed(2)} · {preview.category} · {preview.date}
      </Text>
    </View>
  );
}

function TasksPreviewCard({ preview, colors }: { preview: TaskPreviewItem[]; colors: any }) {
  return (
    <View>
      {preview.map((t, i) => (
        <Text key={i} style={{ color: colors.text, marginBottom: 2 }}>
          {"• "}{t.title}
          {t.due_at ? ` — ${t.due_at.slice(0, 10)}` : ""}
          {t.priority > 0 ? ` [P${t.priority}]` : ""}
          {t.is_recurring ? " 🔁" : ""}
        </Text>
      ))}
    </View>
  );
}

function DomainPreviewCard({
  block, onYes, onNo, confirming, colors,
}: {
  block: DomainBlock; onYes: () => void; onNo: () => void; confirming: boolean; colors: any;
}) {
  const label = block.domain === "health" ? "🍽 Health"
    : block.domain === "finance" ? "💰 Finance" : "✅ Tasks";
  return (
    <View style={{ backgroundColor: colors.card, borderRadius: 12, padding: 16, marginBottom: 12 }}>
      <Text style={{ color: colors.textSecondary, fontSize: 12, marginBottom: 8 }}>{label}</Text>
      {block.domain === "health" && <HealthPreviewCard preview={block.preview as HealthPreview} colors={colors} />}
      {block.domain === "finance" && <FinancePreviewCard preview={block.preview as FinancePreview} colors={colors} />}
      {block.domain === "tasks" && <TasksPreviewCard preview={block.preview as TaskPreviewItem[]} colors={colors} />}
      <View style={{ flexDirection: "row", gap: 12, marginTop: 16 }}>
        {confirming ? (
          <ActivityIndicator color={colors.accent} />
        ) : (
          <>
            <TouchableOpacity
              style={{ flex: 1, backgroundColor: colors.accent, borderRadius: 8, padding: 12, alignItems: "center" }}
              onPress={onYes}
            >
              <Text style={{ color: "#fff", fontWeight: "600" }}>Yes, log it</Text>
            </TouchableOpacity>
            <TouchableOpacity
              style={{ flex: 1, backgroundColor: colors.cardElevated, borderRadius: 8, padding: 12, alignItems: "center" }}
              onPress={onNo}
            >
              <Text style={{ color: colors.text, fontWeight: "600" }}>No, correct</Text>
            </TouchableOpacity>
          </>
        )}
      </View>
    </View>
  );
}

// ── Main component ────────────────────────────────────────────────────────────

export function SmartInputSheet({
  visible, onClose, onConfirmed, domainLock, initialText,
}: SmartInputSheetProps) {
  const { colors } = useTheme();
  const [text, setText] = useState(initialText ?? "");
  const [phase, setPhase] = useState<Phase>({ type: "idle" });
  const correctionRef = useRef("");

  const reset = () => { setText(initialText ?? ""); setPhase({ type: "idle" }); };
  const handleClose = () => { reset(); onClose(); };

  // ── Send ──────────────────────────────────────────────────────────────────
  const handleSend = async (inputText: string) => {
    if (!inputText.trim()) return;
    setPhase({ type: "loading" });
    try {
      let response: ChatResponse;
      if (domainLock) {
        // Fast path: call domain-specific preview endpoint
        const block = await previewDomain(domainLock, inputText.trim());
        response = { prose: "", domains: [block], actions: [] };
      } else {
        response = await chatMessage(inputText.trim());
      }
      if (response.domains.length === 0 && !response.prose) {
        setPhase({ type: "error", message: "Nothing to log. Try again." });
        return;
      }
      setPhase({ type: "preview", response, domainIndex: 0 });
    } catch (e) {
      setPhase({ type: "error", message: e instanceof Error ? e.message : "Failed" });
    }
  };

  // ── Confirm one domain ────────────────────────────────────────────────────
  const handleYes = async (response: ChatResponse, domainIndex: number) => {
    const block = response.domains[domainIndex];
    setPhase({ type: "confirming", response, domainIndex });
    try {
      await confirmDomain(block.domain, block.preview);
      const next = domainIndex + 1;
      if (next < response.domains.length) {
        setPhase({ type: "preview", response, domainIndex: next });
      } else {
        setPhase({ type: "done" });
        onConfirmed();
        setTimeout(() => { reset(); onClose(); }, 1500);
      }
    } catch (e) {
      setPhase({ type: "error", message: e instanceof Error ? e.message : "Confirm failed" });
    }
  };

  // ── Log all domains at once ───────────────────────────────────────────────
  const handleLogAll = async (response: ChatResponse) => {
    setPhase({ type: "loading" });
    try {
      await Promise.all(
        response.domains.map(block => confirmDomain(block.domain, block.preview))
      );
      setPhase({ type: "done" });
      onConfirmed();
      setTimeout(() => { reset(); onClose(); }, 1500);
    } catch (e) {
      setPhase({ type: "error", message: e instanceof Error ? e.message : "Bulk confirm failed" });
    }
  };

  // ── Decline → correct ─────────────────────────────────────────────────────
  const handleNo = (response: ChatResponse, domainIndex: number) => {
    const block = response.domains[domainIndex];
    correctionRef.current = block.extract;
    setPhase({ type: "correcting", domainIndex, prefill: block.extract, response });
  };

  // ── Re-parse just the corrected domain ───────────────────────────────────
  const handleCorrectionSend = async (
    correctedText: string, response: ChatResponse, domainIndex: number
  ) => {
    const block = response.domains[domainIndex];
    setPhase({ type: "loading" });
    try {
      // Call previewDomain directly — domain is already known, no need for global /chat
      const reparsedBlock = await previewDomain(block.domain, correctedText.trim());
      const updatedDomains = [...response.domains];
      updatedDomains[domainIndex] = reparsedBlock;
      setPhase({ type: "preview", response: { ...response, domains: updatedDomains }, domainIndex });
    } catch (e) {
      setPhase({ type: "error", message: "Couldn't re-parse. Try different wording." });
    }
  };

  const s = makeStyles(colors);
  const title = domainLock
    ? domainLock.charAt(0).toUpperCase() + domainLock.slice(1)
    : "Log anything";
  const placeholder = domainLock === "health" ? "What did you eat?"
    : domainLock === "finance" ? "What did you spend?"
    : domainLock === "tasks" ? "What do you need to do?"
    : "Log a meal, expense, task…";

  return (
    <Modal visible={visible} animationType="slide" presentationStyle="pageSheet" onRequestClose={handleClose}>
      <KeyboardAvoidingView behavior={Platform.OS === "ios" ? "padding" : undefined} style={{ flex: 1 }}>
        <View style={s.container}>

          {/* Header */}
          <View style={s.header}>
            <Text style={s.headerTitle}>{title}</Text>
            <TouchableOpacity onPress={handleClose}>
              <Text style={s.cancel}>Cancel</Text>
            </TouchableOpacity>
          </View>

          <ScrollView style={{ flex: 1 }} contentContainerStyle={{ padding: 16 }} keyboardShouldPersistTaps="handled">

            {/* Idle / error */}
            {(phase.type === "idle" || phase.type === "error") && (
              <View>
                {phase.type === "error" && (
                  <Text style={{ color: colors.accentRed, marginBottom: 12 }}>{phase.message}</Text>
                )}
                <TextInput
                  style={s.input}
                  value={text}
                  onChangeText={setText}
                  placeholder={placeholder}
                  placeholderTextColor={colors.textTertiary}
                  multiline
                  autoFocus
                />
                <TouchableOpacity style={s.sendBtn} onPress={() => handleSend(text)}>
                  <Text style={s.sendBtnText}>Send</Text>
                </TouchableOpacity>
              </View>
            )}

            {/* Loading */}
            {phase.type === "loading" && (
              <View style={{ alignItems: "center", paddingTop: 40 }}>
                <ActivityIndicator size="large" color={colors.accent} />
                <Text style={{ color: colors.textSecondary, marginTop: 12 }}>Parsing…</Text>
              </View>
            )}

            {/* Preview */}
            {(phase.type === "preview" || phase.type === "confirming") && (
              <View>
                {/* Prose answer — persists even if user declines a domain write */}
                {phase.response.prose ? (
                  <View style={{ backgroundColor: colors.card, borderRadius: 12, padding: 16, marginBottom: 16 }}>
                    <Text style={{ color: colors.text, lineHeight: 22 }}>{phase.response.prose}</Text>
                    {/* Prose-only: no domains to confirm — show Done */}
                    {phase.response.domains.length === 0 && (
                      <TouchableOpacity
                        style={[s.sendBtn, { marginTop: 16, backgroundColor: colors.cardElevated }]}
                        onPress={handleClose}
                      >
                        <Text style={[s.sendBtnText, { color: colors.text }]}>Done</Text>
                      </TouchableOpacity>
                    )}
                  </View>
                ) : null}

                {/* Action buttons — shown even when prose is empty */}
                {phase.response.actions.length > 0 && (
                  <View style={{ marginBottom: 12 }}>
                    {phase.response.actions.map((action, i) => (
                      <TouchableOpacity key={i} style={s.actionBtn} onPress={() => {
                        setText(action.prefill);
                        setPhase({ type: "idle" });
                      }}>
                        <Text style={{ color: colors.accent }}>+ {action.label}</Text>
                      </TouchableOpacity>
                    ))}
                  </View>
                )}

                {/* "Log all" shortcut when multiple domains */}
                {phase.type === "preview" && phase.response.domains.length > 1 && (
                  <TouchableOpacity
                    style={[s.sendBtn, { marginBottom: 12 }]}
                    onPress={() => handleLogAll(phase.response)}
                  >
                    <Text style={s.sendBtnText}>Log all ({phase.response.domains.length})</Text>
                  </TouchableOpacity>
                )}

                {/* Domain cards */}
                {phase.response.domains.map((block, i) => {
                  if (i < phase.domainIndex) return null; // already confirmed
                  if (i > phase.domainIndex) return (
                    <View key={i} style={{ opacity: 0.3 }}>
                      <View style={{ backgroundColor: colors.card, borderRadius: 12, padding: 16, marginBottom: 12 }}>
                        <Text style={{ color: colors.textSecondary }}>{block.domain} — pending</Text>
                      </View>
                    </View>
                  );
                  return (
                    <DomainPreviewCard
                      key={i}
                      block={block}
                      confirming={phase.type === "confirming" && phase.domainIndex === i}
                      onYes={() => handleYes(phase.response, i)}
                      onNo={() => handleNo(phase.response, i)}
                      colors={colors}
                    />
                  );
                })}
              </View>
            )}

            {/* Correction */}
            {phase.type === "correcting" && (
              <View>
                <Text style={{ color: colors.textSecondary, marginBottom: 8 }}>
                  Correct the {phase.response.domains[phase.domainIndex].domain} entry:
                </Text>
                <TextInput
                  style={s.input}
                  defaultValue={phase.prefill}
                  onChangeText={v => { correctionRef.current = v; }}
                  placeholder="Correct description…"
                  placeholderTextColor={colors.textTertiary}
                  multiline
                  autoFocus
                />
                <TouchableOpacity
                  style={s.sendBtn}
                  onPress={() => handleCorrectionSend(correctionRef.current, phase.response, phase.domainIndex)}
                >
                  <Text style={s.sendBtnText}>Re-parse</Text>
                </TouchableOpacity>
              </View>
            )}

            {/* Done */}
            {phase.type === "done" && (
              <View style={{ alignItems: "center", paddingTop: 40 }}>
                <Text style={{ color: colors.accentGreen, fontSize: 18, fontWeight: "600" }}>Logged ✓</Text>
              </View>
            )}

          </ScrollView>
        </View>
      </KeyboardAvoidingView>
    </Modal>
  );
}

function makeStyles(colors: any) {
  return StyleSheet.create({
    container: { flex: 1, backgroundColor: colors.background },
    header: {
      flexDirection: "row", justifyContent: "space-between", alignItems: "center",
      padding: 16, borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: colors.border,
    },
    headerTitle: { color: colors.text, fontSize: 17, fontWeight: "600" },
    cancel: { color: colors.accent, fontSize: 16 },
    input: {
      backgroundColor: colors.inputBg, borderRadius: 10, padding: 14,
      color: colors.text, fontSize: 16, minHeight: 80, textAlignVertical: "top", marginBottom: 12,
    },
    sendBtn: { backgroundColor: colors.accent, borderRadius: 10, padding: 14, alignItems: "center" },
    sendBtnText: { color: "#fff", fontWeight: "600", fontSize: 16 },
    actionBtn: { marginTop: 12, padding: 8 },
  });
}
