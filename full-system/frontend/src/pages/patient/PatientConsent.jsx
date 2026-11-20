import { useState } from "react";
import { BellRing, Check as CheckIcon, CheckCircle2, Eye, ShieldCheck, ShieldOff, Stethoscope, X, XCircle } from "lucide-react";
import { useAuth, useToast } from "../../context/contexts";
import { api } from "../../lib/api";
import { formatDate } from "../../lib/format";
import { useApi } from "../../hooks/useApi";
import { Button, Card, EmptyState, ErrorState, Loading, Modal, PageHeader, StatusBadge } from "../../components/ui";

export default function PatientConsent() {
  const { user } = useAuth();
  const { showToast } = useToast();
  const pid = user.patient_id;
  const [confirm, setConfirm] = useState(null);
  const [busy, setBusy] = useState(false);
  const { data, loading, error, reload } = useApi(() => api.get(`/patients/${pid}/consent`), [pid]);
  const requests = useApi(() => api.get(`/patients/${pid}/consent-requests`), [pid]);
  const [answering, setAnswering] = useState(null);

  const answer = async (req, approve) => {
    setAnswering(req.id);
    try {
      const res = await api.post(`/patients/${pid}/consent-requests/${req.id}/${approve ? "approve" : "decline"}`);
      showToast(approve ? `${req.doctor.name} can now see your records.` : res.message, approve ? "success" : "info");
    } catch (e) {
      showToast(e.message, "error");
    } finally {
      setAnswering(null);
      requests.reload();
      reload();
    }
  };

  const apply = async () => {
    const { row, grant } = confirm;
    setBusy(true);
    try {
      const res = grant ? await api.post(`/patients/${pid}/consent/${row.doctor.id}`) : await api.del(`/patients/${pid}/consent/${row.doctor.id}`);
      showToast(`${res.message} ${res.access.granted ? "The doctor now has access." : res.access.reason || ""}`, grant ? "success" : "info");
      setConfirm(null);
      reload();
    } catch (e) {
      showToast(e.message, "error");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="space-y-5">
      <PageHeader title="Doctor access" subtitle="You decide which doctors can open your health records. Changes apply straight away." />
      <div className="grid gap-3 rounded-2xl border border-ink-100 bg-white p-4 text-sm shadow-sm sm:grid-cols-2 sm:items-center">
        <p className="flex items-center gap-2.5 text-ink-700"><ShieldCheck size={18} className="shrink-0 text-brand-600" /> You give a doctor permission here</p>
        <p className="flex items-center gap-2.5 font-semibold text-ink-900"><Eye size={18} className="shrink-0 text-green-600" /> = they can see your records, even if they haven&apos;t treated you before</p>
      </div>
      {requests.data?.length > 0 && (
        <Card title="Doctors asking to see your records" subtitle="Allow only doctors you know or were referred to. You can take permission back at any time.">
          <ul className="divide-y divide-ink-100">
            {requests.data.map((req) => (
              <li key={req.id} className="flex flex-wrap items-start gap-3 py-3 first:pt-0 last:pb-0">
                <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-amber-50 text-amber-700"><BellRing size={18} /></span>
                <div className="min-w-[200px] flex-1">
                  <p className="font-semibold text-ink-900">{req.doctor.name}</p>
                  <p className="text-sm text-ink-500">{[req.doctor.specialization, req.doctor.hospital].filter(Boolean).join(" · ")} · asked {formatDate(req.requested_at)}</p>
                  {req.reason && <p className="mt-1 text-sm text-ink-700">&ldquo;{req.reason}&rdquo;</p>}
                </div>
                <div className="flex gap-2">
                  <Button variant="secondary" icon={X} disabled={answering !== null} onClick={() => answer(req, false)}>Decline</Button>
                  <Button icon={CheckIcon} loading={answering === req.id} disabled={answering !== null} onClick={() => answer(req, true)}>Allow</Button>
                </div>
              </li>
            ))}
          </ul>
        </Card>
      )}
      {loading && <Loading />}
      <ErrorState error={error} onRetry={reload} />
      {data?.length === 0 && <Card><EmptyState title="No doctors available" /></Card>}
      <div className="grid gap-4 md:grid-cols-2">
        {data?.map((row) => {
          const granted = row.consent_status === "GRANTED";
          return (
            <Card key={row.doctor.id}>
              <div className="flex items-start justify-between gap-3">
                <div className="flex items-start gap-3">
                  <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-brand-50 text-brand-700"><Stethoscope size={20} /></span>
                  <div>
                    <p className="font-display text-lg font-bold text-ink-900">{row.doctor.name}</p>
                    <p className="text-sm text-ink-500">{[row.doctor.specialization, row.doctor.hospital].filter(Boolean).join(" · ")}</p>
                  </div>
                </div>
                {row.has_access
                  ? <StatusBadge variant="success">Can see your records</StatusBadge>
                  : <StatusBadge variant="neutral">Can&apos;t see your records</StatusBadge>}
              </div>
              <ul className="mt-4 space-y-2 text-sm">
                <Check ok={row.previous_visit} yes={`Has seen you${row.last_visit_date ? ` (last visit ${formatDate(row.last_visit_date)})` : ""}`} no="Hasn't seen you yet" />
                <Check ok={granted} yes={`You gave permission${row.granted_at ? ` on ${formatDate(row.granted_at)}` : ""}`} no={row.consent_status === "REVOKED" ? `You took permission back${row.revoked_at ? ` on ${formatDate(row.revoked_at)}` : ""}` : "You haven't given permission"} />
                {row.doctor.verification_status !== "VERIFIED" && <Check ok={false} no="This doctor isn't verified yet" />}
              </ul>
              <div className="mt-4 flex justify-end border-t border-ink-100 pt-4">
                {granted ? (
                  <Button variant="secondary" icon={ShieldOff} className="text-red-700" onClick={() => setConfirm({ row, grant: false })}>Remove permission</Button>
                ) : (
                  <Button icon={ShieldCheck} onClick={() => setConfirm({ row, grant: true })}>Give permission</Button>
                )}
              </div>
            </Card>
          );
        })}
      </div>
      <Modal open={!!confirm} onClose={() => setConfirm(null)} size="sm" title={confirm?.grant ? "Give permission?" : "Remove permission?"}
        footer={<><Button variant="secondary" onClick={() => setConfirm(null)}>Cancel</Button><Button variant={confirm?.grant ? "primary" : "danger"} loading={busy} onClick={apply}>{confirm?.grant ? "Give permission" : "Remove permission"}</Button></>}>
        <p className="text-sm text-ink-700">
          {confirm?.grant
            ? `${confirm?.row.doctor.name} will be able to view your records, documents and AI summaries straight away.`
            : `${confirm?.row.doctor.name} will immediately lose access to your records, documents and AI summaries.`}
        </p>
      </Modal>
    </div>
  );
}

function Check({ ok, yes, no }) {
  return (
    <li className={`flex items-center gap-2 ${ok ? "text-ink-800" : "text-ink-500"}`}>
      {ok ? <CheckCircle2 size={17} className="shrink-0 text-green-600" /> : <XCircle size={17} className="shrink-0 text-ink-300" />}
      {ok ? yes : no}
    </li>
  );
}
