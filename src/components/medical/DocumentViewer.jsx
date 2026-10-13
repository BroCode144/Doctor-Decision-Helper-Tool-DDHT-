import Modal from "../ui/Modal";
import Button from "../ui/Button";
import { formatDate } from "../../utils/dataHelpers";
import { FileText } from "lucide-react";

export default function DocumentViewer({ document, onClose }) {
  if (!document) return null;

  return (
    <Modal
      open={!!document}
      onClose={onClose}
      title={document.name}
      size="md"
      footer={
        <Button variant="secondary" onClick={onClose}>
          Close
        </Button>
      }
    >
      <div className="rounded-xl border border-ink-100 bg-ink-50/60 p-5">
        <div className="mb-4 flex items-center gap-2 text-ink-400">
          <FileText size={16} />
          <p className="text-xs font-semibold uppercase tracking-wide">
            Simulated document preview
          </p>
        </div>
        <div className="space-y-3 rounded-lg bg-white p-4 font-mono text-sm text-ink-700 shadow-sm">
          {document.preview?.map((line, idx) => <p key={idx}>{line}</p>)}
        </div>
        <dl className="mt-4 grid grid-cols-2 gap-3 text-sm">
          <div>
            <dt className="text-xs font-medium text-ink-400">Type</dt>
            <dd className="font-medium text-ink-800">{document.type}</dd>
          </div>
          <div>
            <dt className="text-xs font-medium text-ink-400">Date</dt>
            <dd className="font-medium text-ink-800">{formatDate(document.date)}</dd>
          </div>
          <div>
            <dt className="text-xs font-medium text-ink-400">Hospital</dt>
            <dd className="font-medium text-ink-800">{document.hospital}</dd>
          </div>
          <div>
            <dt className="text-xs font-medium text-ink-400">Uploaded By</dt>
            <dd className="font-medium text-ink-800">{document.uploadedBy}</dd>
          </div>
        </dl>
      </div>
    </Modal>
  );
}
