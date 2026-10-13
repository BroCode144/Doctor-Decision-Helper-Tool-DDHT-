import { ClipboardList } from "lucide-react";
import { formatDate } from "../../utils/dataHelpers";
import StatusBadge from "../ui/StatusBadge";
import EmptyState from "../ui/EmptyState";

const STATUS_VARIANT = {
  Resolved: "success",
  Managed: "pending",
  Improving: "pending",
  "Under Review": "warning",
};

export default function DiagnosisList({ diagnoses, doctorNameFor }) {
  if (!diagnoses || diagnoses.length === 0) {
    return <EmptyState icon={ClipboardList} message="No diagnoses on record." />;
  }

  return (
    <div className="space-y-3">
      {diagnoses.map((d) => (
        <div key={d.id} className="rounded-2xl border border-ink-100 bg-white p-4 shadow-sm">
          <div className="flex flex-wrap items-start justify-between gap-2">
            <div>
              <p className="font-semibold text-ink-900">{d.diagnosis}</p>
              <p className="mt-0.5 text-sm text-ink-500">
                {formatDate(d.date)} · {doctorNameFor?.(d.doctorId) || "Unknown doctor"}
              </p>
            </div>
            <StatusBadge variant={STATUS_VARIANT[d.status] || "neutral"}>{d.status}</StatusBadge>
          </div>
          {d.notes && <p className="mt-2 text-sm leading-relaxed text-ink-600">{d.notes}</p>}
        </div>
      ))}
    </div>
  );
}
