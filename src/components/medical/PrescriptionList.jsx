import { Pill } from "lucide-react";
import { formatDate } from "../../utils/dataHelpers";
import StatusBadge from "../ui/StatusBadge";
import EmptyState from "../ui/EmptyState";

export default function PrescriptionList({ prescriptions, doctorNameFor }) {
  if (!prescriptions || prescriptions.length === 0) {
    return <EmptyState icon={Pill} message="No prescriptions on record." />;
  }

  return (
    <div className="space-y-3">
      {prescriptions.map((rx) => (
        <div key={rx.id} className="rounded-2xl border border-ink-100 bg-white p-4 shadow-sm">
          <div className="flex flex-wrap items-start justify-between gap-2">
            <div>
              <p className="font-semibold text-ink-900">{rx.medication}</p>
              <p className="mt-0.5 text-sm text-ink-500">
                {formatDate(rx.date)} · {doctorNameFor?.(rx.doctorId) || "Unknown doctor"}
              </p>
            </div>
            <StatusBadge variant={rx.status === "Active" ? "pending" : "success"}>
              {rx.status}
            </StatusBadge>
          </div>
          <div className="mt-2 space-y-0.5 text-sm text-ink-600">
            <p>
              <span className="font-medium text-ink-700">Dosage:</span> {rx.dosage}
            </p>
            <p>
              <span className="font-medium text-ink-700">Instructions:</span> {rx.instructions}
            </p>
          </div>
        </div>
      ))}
    </div>
  );
}
