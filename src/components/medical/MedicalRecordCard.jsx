import { Eye } from "lucide-react";
import { formatDate } from "../../utils/dataHelpers";
import { typeIcon, typeTone } from "./recordMeta";
import StatusBadge from "../ui/StatusBadge";
import Button from "../ui/Button";

export default function MedicalRecordCard({ record, doctorName, onView }) {
  const Icon = typeIcon(record.type);

  return (
    <div className="flex flex-col gap-3 rounded-2xl border border-ink-100 bg-white p-4 shadow-sm sm:flex-row sm:items-center sm:justify-between">
      <div className="flex items-start gap-3">
        <div className={`rounded-xl p-2.5 ${typeTone(record.type)}`}>
          <Icon size={18} />
        </div>
        <div>
          <p className="font-semibold text-ink-900">{record.documentName}</p>
          <p className="mt-0.5 text-sm text-ink-500">
            {record.type} · {formatDate(record.date)}
          </p>
          <p className="text-xs text-ink-400">
            {doctorName ? `${doctorName} · ` : ""}
            {record.hospital}
          </p>
        </div>
      </div>
      <div className="flex items-center gap-2 sm:flex-col sm:items-end">
        <StatusBadge variant={record.status === "Active" ? "success" : "neutral"}>
          {record.status}
        </StatusBadge>
        {onView && (
          <Button variant="secondary" size="sm" icon={Eye} onClick={() => onView(record)}>
            View
          </Button>
        )}
      </div>
    </div>
  );
}
