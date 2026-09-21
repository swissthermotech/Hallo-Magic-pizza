export function statusTone(s: string): "neutral" | "brand" | "success" | "warning" | "error" | "inverse" {
  if (s === "pending") return "warning";
  if (s === "cancelled") return "error";
  if (s === "completed" || s === "delivered" || s === "picked_up") return "neutral";
  if (s === "ready" || s === "delivering") return "success";
  return "brand";
}

export const chf = (n: number) => `CHF ${n.toFixed(2)}`;

/** Backend stores naive UTC datetimes; make sure we parse them as UTC. */
export function parseUTC(s?: string | null): Date | null {
  if (!s) return null;
  const hasTz = /Z$|[+-]\d\d:\d\d$/.test(s);
  return new Date(hasTz ? s : `${s}Z`);
}

export function fmtTime(s?: string | null): string {
  const d = parseUTC(s);
  if (!d || isNaN(d.getTime())) return "--:--";
  return d.toLocaleTimeString("fr-CH", { hour: "2-digit", minute: "2-digit", timeZone: "Europe/Zurich" });
}

export function fmtDate(s?: string | null): string {
  const d = parseUTC(s);
  if (!d || isNaN(d.getTime())) return "—";
  return d.toLocaleDateString("fr-CH", { day: "2-digit", month: "2-digit", year: "numeric", timeZone: "Europe/Zurich" });
}

export function minutesUntil(s?: string | null): number | null {
  const d = parseUTC(s);
  if (!d) return null;
  return Math.round((d.getTime() - Date.now()) / 60000);
}

export function elapsedMinutes(s?: string | null): number {
  const d = parseUTC(s);
  if (!d) return 0;
  return Math.max(0, Math.floor((Date.now() - d.getTime()) / 60000));
}
