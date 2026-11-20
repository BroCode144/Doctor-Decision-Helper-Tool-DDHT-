export const RECORD_TYPES = [
  { value: "CONSULTATION", label: "Consultation" },
  { value: "DIAGNOSIS", label: "Diagnosis" },
  { value: "PRESCRIPTION", label: "Prescription" },
  { value: "LAB_REPORT", label: "Lab Report" },
  { value: "IMAGING", label: "Imaging" },
  { value: "DISCHARGE_SUMMARY", label: "Discharge Summary" },
  { value: "MEDICAL_HISTORY", label: "Medical History" },
  { value: "OTHER", label: "Other" },
];

export const recordTypeLabel = (v) => RECORD_TYPES.find((t) => t.value === v)?.label || v;

export function formatDate(value) {
  if (!value) return "—";
  const d = new Date(value.length === 10 ? `${value}T00:00:00` : value);
  if (Number.isNaN(d.getTime())) return value;
  return d.toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" });
}

export function formatDateTime(value) {
  if (!value) return "—";
  const d = new Date(value);
  return d.toLocaleString(undefined, { year: "numeric", month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" });
}

export function formatBytes(n) {
  if (!n && n !== 0) return "—";
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  return `${(n / 1024 / 1024).toFixed(1)} MB`;
}

export function initials(name = "") {
  return name
    .replace(/^Dr\.\s*/, "")
    .split(" ")
    .map((w) => w[0])
    .slice(0, 2)
    .join("")
    .toUpperCase();
}

/** Today's date (YYYY-MM-DD) in the user's local time zone, not UTC. */
export const todayISO = () => {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
};
