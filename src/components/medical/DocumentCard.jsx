import { Eye, Trash2 } from "lucide-react";
import { formatDate } from "../../utils/dataHelpers";
import { typeIcon, typeTone } from "./recordMeta";
import StatusBadge from "../ui/StatusBadge";
import Button from "../ui/Button";

// onDelete is optional: pass it only where the viewer is allowed to delete
// this document (a patient's own upload). Without it, no Delete button shows.
export default function DocumentCard({ document, onView, onDelete }) {
  const Icon = typeIcon(document.type);

  return (
    <div className="flex flex-col gap-3 rounded-2xl border border-ink-100 bg-white p-4 shadow-sm">
      <div className="flex items-start justify-between gap-3">
        <div className={`rounded-xl p-2.5 ${typeTone(document.type)}`}>
          <Icon size={18} />
        </div>
        <StatusBadge variant={document.status === "Active" ? "success" : "neutral"}>
          {document.status}
        </StatusBadge>
      </div>
      <div>
        <p className="font-semibold text-ink-900">{document.name}</p>
        <p className="mt-0.5 text-sm text-ink-500">
          {document.type} · {formatDate(document.date)}
        </p>
        <p className="text-xs text-ink-400">{document.hospital}</p>
        <p className="mt-1 text-xs text-ink-400">Uploaded by {document.uploadedBy}</p>
      </div>
      <div className="flex gap-2">
        <Button
          variant="secondary"
          size="sm"
          icon={Eye}
          onClick={() => onView(document)}
          className="flex-1"
        >
          View Document
        </Button>
        {onDelete && (
          <Button variant="danger" size="sm" icon={Trash2} onClick={() => onDelete(document)}>
            Delete
          </Button>
        )}
      </div>
    </div>
  );
}
