// Appointment times come from the API in UTC and are shown in the viewer's own time zone.

export const viewerTimeZone = () => Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC";

export const fmtTime = (iso) => new Date(iso).toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit" });

export const fmtDay = (iso) =>
  new Date(iso).toLocaleDateString(undefined, { weekday: "short", day: "numeric", month: "short" });

export const fmtDayLong = (iso) =>
  new Date(iso).toLocaleDateString(undefined, { weekday: "long", day: "numeric", month: "long", year: "numeric" });

export const fmtSlot = (startIso, endIso) => `${fmtDayLong(startIso)}, ${fmtTime(startIso)} – ${fmtTime(endIso)}`;

/** YYYY-MM-DD of an instant in the viewer's time zone (for grouping slots by day). */
export function localDayKey(iso) {
  const d = new Date(iso);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

/** "in 3 days", "in 2 hours", "5 minutes ago" */
export function relative(iso, now) {
  const diff = (new Date(iso).getTime() - now) / 1000;
  const abs = Math.abs(diff);
  const rtf = new Intl.RelativeTimeFormat(undefined, { numeric: "auto" });
  if (abs < 3600) return rtf.format(Math.round(diff / 60), "minute");
  if (abs < 86400) return rtf.format(Math.round(diff / 3600), "hour");
  return rtf.format(Math.round(diff / 86400), "day");
}

export const WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];

export const APPOINTMENT_STATUS = {
  REQUESTED: { label: "Awaiting doctor", variant: "pending" },
  CONFIRMED: { label: "Confirmed", variant: "success" },
  RESCHEDULED: { label: "Moved", variant: "neutral" },
  CANCELLED: { label: "Cancelled", variant: "danger" },
  IN_PROGRESS: { label: "In progress", variant: "pending" },
  COMPLETED: { label: "Completed", variant: "success" },
  NO_SHOW: { label: "No-show", variant: "warning" },
};
