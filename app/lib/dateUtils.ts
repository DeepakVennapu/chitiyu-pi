/**
 * Returns today's date as YYYY-MM-DD in device local time.
 * Use this everywhere you need "today" as a date string.
 */
export function todayLocal(): string {
  const d = new Date();
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

/**
 * Returns the current local datetime as an ISO string to send to the backend.
 * Backend will convert it to local time via to_local_ts().
 */
export function nowISO(): string {
  return new Date().toISOString();
}

/**
 * Parse a stored "YYYY-MM-DD HH:MM:SS" local timestamp from the DB into a JS Date.
 * DB stores local time (no tz marker), so we parse it as local — no Z appended.
 */
export function parseLocalTs(raw: string | null | undefined): Date | null {
  if (!raw) return null;
  // If it already has tz info, parse as-is
  if (raw.includes("Z") || raw.includes("+")) return new Date(raw);
  // Bare string — treat as local time (replace space with T, no Z)
  const d = new Date(raw.replace(" ", "T"));
  return isNaN(d.getTime()) ? null : d;
}

/**
 * Format a local timestamp for display as time only (e.g. "6:38 PM").
 */
export function formatTime(raw: string | null | undefined): string {
  const d = parseLocalTs(raw);
  if (!d) return "";
  return d.toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit" });
}

/**
 * Format a Date as YYYY-MM-DD in local time.
 */
export function dateToLocal(d: Date): string {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

/**
 * Build a local ISO datetime string for a given date and meal-time slot.
 * e.g. slotISO(new Date(), "breakfast") → "2026-08-15T08:00:00"
 */
export function slotISO(date: Date | string, slot: string): string {
  const slotHours: Record<string, number> = {
    breakfast: 8,
    lunch: 12,
    dinner: 18,
    snack: 15,
  };
  const hour = slotHours[slot] ?? 12;
  const d = typeof date === "string" ? new Date(date + "T12:00:00") : new Date(date);
  d.setHours(hour, 0, 0, 0);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}T${String(hour).padStart(2, "0")}:00:00`;
}
