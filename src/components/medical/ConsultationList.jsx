import { Stethoscope } from "lucide-react";
import { formatDate } from "../../utils/dataHelpers";
import StatusBadge from "../ui/StatusBadge";
import EmptyState from "../ui/EmptyState";

export default function ConsultationList({ consultations, doctorNameFor }) {
  if (!consultations || consultations.length === 0) {
    return <EmptyState icon={Stethoscope} message="No consultation records available." />;
  }

  return (
    <div className="space-y-3">
      {consultations.map((c) => (
        <div key={c.id} className="rounded-2xl border border-ink-100 bg-white p-4 shadow-sm">
          <div className="flex flex-wrap items-start justify-between gap-2">
            <div>
              <p className="font-semibold text-ink-900">{c.reason}</p>
              <p className="mt-0.5 text-sm text-ink-500">
                {formatDate(c.date)} · {doctorNameFor?.(c.doctorId) || "Unknown doctor"} ·{" "}
                {c.hospital}
              </p>
            </div>
            <StatusBadge variant={c.followUp === "None" ? "neutral" : "pending"}>
              {c.followUp === "None" ? "No follow-up" : c.followUp}
            </StatusBadge>
          </div>
          {c.notes && <p className="mt-2 text-sm leading-relaxed text-ink-600">{c.notes}</p>}
        </div>
      ))}
    </div>
  );
}
