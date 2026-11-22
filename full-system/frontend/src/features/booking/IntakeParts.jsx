import { AlertTriangle, ClipboardList, HeartPulse, Stethoscope, UserRound } from "lucide-react";
import { formatDateTime } from "../../lib/format";

const AUTHOR = {
  PATIENT: { label: "Patient", icon: UserRound, tone: "bg-sky-50 text-sky-700" },
  RECEPTION: { label: "Reception", icon: ClipboardList, tone: "bg-amber-50 text-amber-700" },
  DOCTOR: { label: "Doctor", icon: Stethoscope, tone: "bg-brand-50 text-brand-700" },
};

const VITAL_LABELS = [
  ["systolic_bp", "BP", (v) => `${v.systolic_bp}${v.diastolic_bp ? `/${v.diastolic_bp}` : ""} mmHg`],
  ["pulse", "Pulse", (v) => `${v.pulse} /min`],
  ["temperature_c", "Temp", (v) => `${v.temperature_c} °C`],
  ["spo2", "SpO₂", (v) => `${v.spo2}%`],
  ["weight_kg", "Weight", (v) => `${v.weight_kg} kg`],
  ["height_cm", "Height", (v) => `${v.height_cm} cm`],
];

/** Warning signs from the checklist or dangerous vitals. Shown first, in red. */
export function UrgentBanner({ urgent }) {
  if (!urgent?.length) return null;
  return (
    <div role="alert" className="flex gap-3 rounded-xl border-2 border-red-200 bg-red-50 p-3 text-sm text-red-800">
      <AlertTriangle size={20} className="mt-0.5 shrink-0" />
      <div>
        <p className="font-bold">Warning signs</p>
        <ul className="mt-0.5 list-disc pl-4">{urgent.map((u) => <li key={u}>{u}</li>)}</ul>
      </div>
    </div>
  );
}

/** Symptoms in the order they were written, each labelled with who wrote it and when. */
export function SymptomList({ entries, empty = "No symptoms recorded yet.", className = "space-y-2" }) {
  if (!entries?.length) return <p className="text-sm text-ink-500">{empty}</p>;
  return (
    <ul className={className}>
      {entries.map((e) => {
        const a = AUTHOR[e.author_role] || AUTHOR.DOCTOR;
        const Icon = a.icon;
        return (
          <li key={e.id} className="flex gap-3 rounded-xl border border-ink-100 bg-white p-3">
            <span className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-lg ${a.tone}`}><Icon size={16} /></span>
            <div className="min-w-0 flex-1">
              <p className="text-xs text-ink-500">
                <span className="font-semibold text-ink-700">{a.label}{e.from_booking ? " (when booking)" : ""}</span>
                {e.author_name && ` · ${e.author_name}`} · {formatDateTime(e.created_at)}
              </p>
              <p className="mt-0.5 text-sm text-ink-800">{e.text}</p>
              {(e.duration || e.severity) && (
                <p className="mt-0.5 text-xs text-ink-500">{[e.duration && `For ${e.duration}`, e.severity].filter(Boolean).join(" · ")}</p>
              )}
              {e.red_flags?.length > 0 && (
                <p className="mt-1 text-xs font-semibold text-red-700">{e.red_flags.map((f) => f.label).join(" · ")}</p>
              )}
            </div>
          </li>
        );
      })}
    </ul>
  );
}

/** One set of vitals as small labelled values; dangerous values in red. */
export function VitalsRow({ vitals }) {
  if (!vitals) return null;
  const shown = VITAL_LABELS.filter(([k]) => vitals[k] !== null && vitals[k] !== undefined);
  return (
    <div className="rounded-xl border border-ink-100 bg-white p-3">
      <p className="flex items-center gap-1.5 text-xs text-ink-500">
        <HeartPulse size={14} className="text-ink-400" />
        Vitals · {vitals.recorded_by_role === "RECEPTION" ? "reception" : vitals.recorded_by_role?.toLowerCase()}
        {vitals.recorded_by_name && ` (${vitals.recorded_by_name})`} · {formatDateTime(vitals.measured_at)}
      </p>
      <div className="mt-2 flex flex-wrap gap-2">
        {shown.map(([k, label, fmt]) => (
          <span key={k} className="rounded-lg bg-ink-50 px-2.5 py-1 text-sm text-ink-800">
            <span className="text-xs text-ink-500">{label} </span>{fmt(vitals)}
          </span>
        ))}
      </div>
      {vitals.warnings?.length > 0 && <p className="mt-2 text-xs font-semibold text-red-700">{vitals.warnings.join(" · ")}</p>}
    </div>
  );
}

/** The patient's answers to the booking questions, plus the chest-pain type worked out from them. Closed by default: the doctor opens it with the arrow. */
export function BookingAnswers({ answers }) {
  if (!answers) return null;
  return (
    <details className="rounded-xl border border-sky-100 bg-sky-50/50 p-3">
      <summary className="cursor-pointer text-xs text-ink-500">
        <UserRound size={14} className="mr-1 inline align-[-2px] text-sky-600" />
        <span className="font-semibold text-ink-700">Patient&apos;s answers when booking</span> · {formatDateTime(answers.created_at)}
      </summary>
      <dl className="mt-2 grid gap-x-4 gap-y-1 text-sm sm:grid-cols-2">
        {answers.items.map((i) => (
          <div key={i.label} className="flex justify-between gap-2 border-b border-sky-100/70 py-0.5">
            <dt className="text-ink-500">{i.label}</dt><dd className="font-semibold text-ink-800">{i.value}</dd>
          </div>
        ))}
      </dl>
      {answers.chest_pain_type && (
        <p className="mt-2 text-xs text-ink-600">
          <span className="font-semibold">Chest-pain type (worked out, check with the patient): {answers.chest_pain_type.label}</span> · {answers.chest_pain_type.why}
        </p>
      )}
    </details>
  );
}

/** What the patient told the intake chat (saved with the booking, with their consent), grouped by section. */
export function IntakeRecordView({ record }) {
  if (!record) return null;
  return (
    <details className="rounded-xl border border-brand-100 bg-brand-50/40 p-3">
      <summary className="cursor-pointer text-xs text-ink-500">
        <span className="font-semibold text-ink-700">Patient&apos;s intake (chat and form)</span> · {formatDateTime(record.created_at)}
        {record.red_flag && <span className="ml-2 rounded bg-red-100 px-1.5 py-0.5 font-semibold text-red-800">Warning signs confirmed: {record.red_flags.join(", ")}</span>}
      </summary>
      <div className="mt-2 space-y-3">
        {record.sections.map((s) => (
          <div key={s.id}>
            <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-ink-500">{s.title}</p>
            <dl className="grid gap-x-4 gap-y-1 text-sm sm:grid-cols-2">
              {s.items.map((i) => (
                <div key={i.field} className="flex justify-between gap-2 border-b border-brand-100/70 py-0.5">
                  <dt className="text-ink-500">{i.label}</dt><dd className="text-right font-semibold text-ink-800">{i.value}</dd>
                </div>
              ))}
            </dl>
          </div>
        ))}
        {record.codes.length > 0 && (
          <p className="text-xs text-ink-600">
            <span className="font-semibold">Symptom codes (fixed table, please verify):</span>{" "}
            {record.codes.map((c) => `${c.display}${c.snomed_ct ? ` · SNOMED ${c.snomed_ct}` : ""}${c.icd10 ? ` · ICD-10 ${c.icd10}` : ""}`).join("; ")}
          </p>
        )}
      </div>
    </details>
  );
}
