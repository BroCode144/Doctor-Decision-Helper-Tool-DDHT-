import { Stethoscope, Pill, ClipboardList, FlaskConical, ScanLine, FileText } from "lucide-react";

export const TYPE_ICON = {
  Consultation: Stethoscope,
  Prescription: Pill,
  Diagnosis: ClipboardList,
  "Lab Report": FlaskConical,
  Imaging: ScanLine,
  Other: FileText,
};

export const TYPE_TONE = {
  Consultation: "bg-sky-50 text-sky-600",
  Prescription: "bg-brand-50 text-brand-600",
  Diagnosis: "bg-amber-50 text-amber-600",
  "Lab Report": "bg-violet-50 text-violet-600",
  Imaging: "bg-rose-50 text-rose-600",
  Other: "bg-ink-100 text-ink-600",
};

export function typeIcon(type) {
  return TYPE_ICON[type] || FileText;
}

export function typeTone(type) {
  return TYPE_TONE[type] || TYPE_TONE.Other;
}
