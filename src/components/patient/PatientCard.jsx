import { ChevronRight } from "lucide-react";
import { calculateAge } from "../../utils/dataHelpers";

export default function PatientCard({ patient, onClick }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="flex w-full items-center gap-4 rounded-2xl border border-ink-100 bg-white p-4 text-left shadow-sm transition-colors hover:border-brand-200 hover:bg-brand-50/40"
    >
      <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-full bg-brand-100 text-sm font-bold text-brand-700">
        {patient.initials}
      </div>
      <div className="min-w-0 flex-1">
        <p className="font-semibold text-ink-900">{patient.name}</p>
        <p className="text-sm text-ink-500">
          {patient.id} · {calculateAge(patient.dob)} yrs · {patient.gender}
        </p>
      </div>
      <ChevronRight size={18} className="shrink-0 text-ink-300" />
    </button>
  );
}
