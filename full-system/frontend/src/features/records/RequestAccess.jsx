import { useState } from "react";
import { Clock, Send, XCircle } from "lucide-react";
import { useToast } from "../../context/contexts";
import { api } from "../../lib/api";
import { formatDate } from "../../lib/format";
import { Button, inputCls } from "../../components/ui";

/**
 * A doctor without access asks the patient for permission. The server decides whether a request is allowed
 * (`state` comes from GET /patients/{id}/access): one open request at a time, and a 7-day wait after a decline.
 */
export default function RequestAccess({ patientId, state, onSent }) {
  const { showToast } = useToast();
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);

  if (!state) return null;
  if (state.status === "PENDING") {
    return (
      <Note icon={Clock} tone="text-amber-700">
        Access requested on {formatDate(state.requested_at)}. The patient has been notified; you&apos;ll get a notification when they answer.
      </Note>
    );
  }
  if (state.retry_after) {
    return (
      <Note icon={XCircle} tone="text-red-700">
        The patient declined your request on {formatDate(state.responded_at)}. You can ask again from {formatDate(state.retry_after)}.
      </Note>
    );
  }
  if (!state.can_request) return null;

  const send = async (e) => {
    e.preventDefault();
    setBusy(true);
    try {
      const res = await api.post(`/patients/${patientId}/consent-requests`, { reason: reason.trim() || null });
      showToast(res.message, "success");
      onSent?.();
    } catch (err) {
      showToast(err.message, "error");
      onSent?.();
    } finally {
      setBusy(false);
    }
  };

  return (
    <form onSubmit={send} className="mt-4 rounded-xl border border-brand-100 bg-brand-50/50 p-4">
      <p className="text-sm font-semibold text-ink-800">Ask the patient for access</p>
      <p className="mt-0.5 text-xs text-ink-500">They get a notification and can allow or decline. Your note is shown only inside their account.</p>
      <label htmlFor="access-reason" className="sr-only">Note to the patient (optional)</label>
      <textarea id="access-reason" value={reason} onChange={(e) => setReason(e.target.value)} maxLength={300} rows={2}
        placeholder="Optional note, e.g. Referred to me for a second opinion" className={`${inputCls} mt-3 resize-none`} />
      <div className="mt-3 flex items-center justify-between gap-3">
        <span className="text-xs text-ink-400">{reason.length}/300</span>
        <Button type="submit" icon={Send} loading={busy}>Request access</Button>
      </div>
    </form>
  );
}

function Note({ icon: Icon, tone, children }) {
  return (
    <p className={`mt-4 flex items-start gap-2 rounded-xl bg-ink-50 p-3 text-sm ${tone}`}>
      <Icon size={17} className="mt-0.5 shrink-0" />
      <span>{children}</span>
    </p>
  );
}
