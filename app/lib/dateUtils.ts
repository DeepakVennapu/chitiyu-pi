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
