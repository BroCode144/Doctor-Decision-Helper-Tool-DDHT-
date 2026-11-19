import { useState } from "react";
import { Trash2 } from "lucide-react";
import { useAuth, useToast } from "../../context/contexts";
import { api } from "../../lib/api";
import { formatDateTime } from "../../lib/format";
import { Button, Field, Modal, inputCls } from "../../components/ui";

/**
 * "Delete" for an upload. Shown only when the server would allow it:
 * the uploader within the undo window, or an administrator (who must give a reason).
 * The server enforces the same rules.
 */
export default function DeleteUploadButton({ documentId, title, uploadedByUserId, deletableUntil, onDeleted, size = "sm" }) {
  const { user } = useAuth();
  const { showToast } = useToast();
  const [open, setOpen] = useState(false);
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [now] = useState(() => Date.now()); // read the clock once, not on every render
  const isAdmin = user?.role === "ADMIN";
  const withinWindow = deletableUntil && now < new Date(deletableUntil).getTime();
  if (!documentId || !(isAdmin || (user?.id === uploadedByUserId && withinWindow))) return null;

  const remove = async () => {
    setBusy(true);
    try {
      const res = await api.del(`/documents/${documentId}`, isAdmin ? { reason } : undefined);
      showToast(res.message, "success");
      setOpen(false);
      onDeleted?.(documentId);
    } catch (e) {
      showToast(e.message, "error");
    } finally {
      setBusy(false);
    }
  };

  return (
    <>
      <Button size={size} variant="ghost" icon={Trash2} className="text-red-600 hover:bg-red-50" onClick={() => setOpen(true)}>
        Delete
      </Button>
      <Modal open={open} onClose={() => setOpen(false)} size="sm" title="Delete this upload?"
        footer={<>
          <Button variant="secondary" onClick={() => setOpen(false)}>Cancel</Button>
          <Button variant="danger" icon={Trash2} loading={busy} disabled={isAdmin && reason.trim().length < 10} onClick={remove}>Delete permanently</Button>
        </>}>
        <div className="space-y-3 text-sm text-ink-700">
          <p><strong>{title}</strong> will be permanently removed: the file, its text and its AI search data. Doctors and the AI will no longer see it.</p>
          <p className="text-xs text-ink-500">Use this for mistakes (wrong file, someone else&apos;s report, duplicate). The deletion is recorded in the audit log.</p>
          {!isAdmin && deletableUntil && <p className="text-xs text-ink-500">You can delete your own uploads until {formatDateTime(deletableUntil)}.</p>}
          {isAdmin && (
            <Field label="Reason (recorded in the audit log)" required hint="At least 10 characters.">
              <textarea className={inputCls} rows={2} value={reason} onChange={(e) => setReason(e.target.value)} maxLength={500}
                placeholder="e.g. Patient reported this file belongs to someone else" />
            </Field>
          )}
        </div>
      </Modal>
    </>
  );
}
