import { useState } from "react";
import { AlertTriangle, BadgeCheck, CheckCircle2, CircleHelp, ExternalLink, FileText, MailQuestion, XCircle } from "lucide-react";
import { useToast } from "../../context/contexts";
import { api } from "../../lib/api";
import { formatDateTime } from "../../lib/format";
import { useApi } from "../../hooks/useApi";
import { Button, Card, EmptyState, ErrorState, Field, Loading, Modal, PageHeader, StatusBadge, Tabs, inputCls } from "../../components/ui";
import { STATUS_LABEL, openApplicationFile } from "./api";

const RESULT = {
  ok: { icon: CheckCircle2, cls: "text-green-700" },
  warn: { icon: AlertTriangle, cls: "text-amber-700" },
  fail: { icon: XCircle, cls: "text-red-700" },
  unknown: { icon: CircleHelp, cls: "text-ink-500" },
};

function Badge({ status }) {
  const s = STATUS_LABEL[status] || { label: status, variant: "neutral" };
  return <StatusBadge variant={s.variant}>{s.label}</StatusBadge>;
}

function CheckRow({ c }) {
  const r = RESULT[c.result] || RESULT.unknown;
  const Icon = r.icon;
  return (
    <li className="flex gap-2 text-sm">
      <Icon size={16} className={`mt-0.5 shrink-0 ${r.cls}`} />
      <span><span className="font-semibold text-ink-800">{c.label}</span>{c.detail && <span className="text-ink-500"> · {c.detail}</span>}</span>
    </li>
  );
}

/** Admin queue: the automatic checklist first, then a quick check on the NMC register, then a decision. */
export default function AdminDoctorApplications() {
  const [status, setStatus] = useState("UNDER_REVIEW");
  const [open, setOpen] = useState(null);
  const list = useApi(() => api.get("/admin/doctor-applications", { status: status || undefined }), [status]);
  return (
    <div className="space-y-4">
      <PageHeader title="Doctor applications" subtitle="New doctors get an account only after you approve. Check the number on the NMC register before approving." />
      <Tabs active={status} onChange={setStatus} tabs={[{ value: "UNDER_REVIEW", label: "To review" }, { value: "NEEDS_INFO", label: "Waiting for doctor" },
        { value: "CHECKING", label: "Being checked" }, { value: "APPROVED", label: "Approved" }, { value: "REJECTED", label: "Rejected" }, { value: "", label: "All" }]} />
      {list.loading && <Loading />}
      <ErrorState error={list.error} onRetry={list.reload} />
      {list.data?.length === 0 && <Card><EmptyState title="No applications here" /></Card>}
      <div className="grid gap-3 md:grid-cols-2">
        {list.data?.map((a) => (
          <button key={a.id} type="button" onClick={() => setOpen(a.id)} className="rounded-2xl border border-ink-100 bg-white p-4 text-left shadow-sm transition hover:border-brand-300">
            <div className="flex items-start justify-between gap-2">
              <div>
                <p className="font-display text-base font-bold text-ink-900">{a.full_name}</p>
                <p className="text-sm text-ink-500">{a.specialization} · {a.council.name}</p>
                <p className="text-xs text-ink-400">{a.id} · Reg. {a.registration_number} ({a.registration_year}) · {formatDateTime(a.created_at)}</p>
              </div>
              <Badge status={a.status} />
            </div>
            {a.counts && (
              <p className="mt-2 flex gap-3 text-xs">
                <span className="text-green-700">{a.counts.ok} ok</span>
                {a.counts.warn > 0 && <span className="text-amber-700">{a.counts.warn} to look at</span>}
                {a.counts.fail > 0 && <span className="font-semibold text-red-700">{a.counts.fail} failed</span>}
                {a.counts.unknown > 0 && <span className="text-ink-500">{a.counts.unknown} not read</span>}
              </p>
            )}
          </button>
        ))}
      </div>
      {open && <Detail id={open} onClose={() => setOpen(null)} onChanged={() => { setOpen(null); list.reload(); }} />}
    </div>
  );
}

function Detail({ id, onClose, onChanged }) {
  const { showToast } = useToast();
  const { data, loading, error } = useApi(() => api.get(`/admin/doctor-applications/${id}`), [id]);
  const [mode, setMode] = useState(null); // approve | info | reject
  const [text, setText] = useState("");
  const [kinds, setKinds] = useState([]);
  const [busy, setBusy] = useState(false);

  const act = async () => {
    setBusy(true);
    try {
      if (mode === "approve") await api.post(`/admin/doctor-applications/${id}/approve`, { note: text || null });
      if (mode === "reject") await api.post(`/admin/doctor-applications/${id}/reject`, { reason: text });
      if (mode === "info") await api.post(`/admin/doctor-applications/${id}/request-info`, { kinds, message: text });
      showToast({ approve: "Approved. The doctor has been emailed a link to set their password.", reject: "Rejected. The doctor has been emailed the reason.",
        info: "Asked for more. The doctor has been emailed an upload link." }[mode], "success");
      onChanged();
    } catch (e) {
      showToast(e.message, "error");
    } finally {
      setBusy(false);
    }
  };
  const open = async (docId) => {
    try {
      await openApplicationFile(id, docId);
    } catch (e) {
      showToast(e.message, "error");
    }
  };
  const decidable = data && ["UNDER_REVIEW", "NEEDS_INFO"].includes(data.status);
  const copy = (v) => navigator.clipboard?.writeText(v).then(() => showToast("Registration number copied.", "success"), () => {});

  return (
    <Modal open onClose={onClose} size="lg" title={data ? `${data.full_name} · ${data.id}` : "Application"}
      footer={decidable && !mode ? <>
        <Button variant="secondary" icon={XCircle} onClick={() => { setMode("reject"); setText(""); }}>Reject</Button>
        <Button variant="secondary" icon={MailQuestion} onClick={() => { setMode("info"); setText(""); setKinds([]); }}>Ask for more</Button>
        <Button icon={BadgeCheck} onClick={() => { setMode("approve"); setText(""); }}>Approve</Button>
      </> : mode ? <>
        <Button variant="secondary" onClick={() => setMode(null)}>Back</Button>
        <Button loading={busy} variant={mode === "reject" ? "danger" : "primary"} disabled={(mode !== "approve" && text.trim().length < 5) || (mode === "info" && !kinds.length)} onClick={act}>
          {{ approve: "Approve and email the doctor", reject: "Reject and email the reason", info: "Email the upload link" }[mode]}
        </Button>
      </> : null}>
      {loading && <Loading />}
      <ErrorState error={error} />
      {data && !mode && (
        <div className="space-y-5">
          <div className="flex flex-wrap items-center gap-2"><Badge status={data.status} />
            {data.decision_note && <span className="text-xs text-ink-500">Note: {data.decision_note}</span>}
            {data.info_request && <span className="text-xs text-amber-700">Waiting for: {data.info_request.kinds.join(", ")} ({data.info_request.by})</span>}
          </div>
          <dl className="grid gap-x-6 gap-y-1 text-sm sm:grid-cols-2">
            {[["Email", data.email], ["Phone", data.phone || "-"], ["Specialization", data.specialization], ["Qualification", data.qualification],
              ["Council", data.council.name], ["Registration", `${data.registration_number} (${data.registration_year})`],
              ["Specialist", data.claims_specialist ? "Yes (PG degree required)" : "No"], ["Hospital", data.hospital?.name || "-"]].map(([k, v]) => (
              <div key={k} className="flex justify-between gap-2 border-b border-ink-50 py-1"><dt className="text-ink-500">{k}</dt><dd className="text-right font-semibold text-ink-800">{v}</dd></div>
            ))}
          </dl>
          <div className="flex flex-wrap items-center gap-2 rounded-xl bg-sky-50 p-3 text-sm text-sky-900">
            <span className="flex-1">Search <b>{data.registration_number}</b> on the NMC Indian Medical Register and compare the name and council.</span>
            <Button size="sm" variant="secondary" onClick={() => copy(data.registration_number)}>Copy number</Button>
            <a href={data.nmc_register_url} target="_blank" rel="noreferrer noopener" className="inline-flex items-center gap-1 rounded-lg bg-white px-3 py-1.5 text-sm font-semibold text-sky-800 ring-1 ring-sky-200 hover:bg-sky-100">
              Open NMC register <ExternalLink size={14} />
            </a>
          </div>
          {data.checks ? (
            <section className="space-y-3">
              <p className="text-sm font-semibold text-ink-700">Automatic checks</p>
              <ul className="space-y-1.5">{data.checks.overall.map((c) => <CheckRow key={c.label} c={c} />)}</ul>
              {data.documents.filter((d) => !d.superseded).map((d) => (
                <div key={d.id} className="rounded-xl border border-ink-100 p-3">
                  <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
                    <p className="flex items-center gap-1.5 text-sm font-semibold text-ink-900"><FileText size={15} className="text-ink-400" /> {d.title}</p>
                    <span className="flex items-center gap-2 text-xs text-ink-500">
                      {d.read_method && <span>read from: {d.read_method}</span>}
                      {d.deleted ? <span>file deleted after decision</span> : <Button size="sm" variant="secondary" onClick={() => open(d.id)}>Open file</Button>}
                    </span>
                  </div>
                  <ul className="space-y-1">{(d.check?.checks || []).map((c) => <CheckRow key={c.label} c={c} />)}</ul>
                </div>
              ))}
              <p className="text-xs text-ink-400">These checks catch wrong files and mismatches; they cannot spot a well-made forgery. The NMC register is the real check.</p>
            </section>
          ) : <p className="text-sm text-ink-500">The documents are still being checked. Open this again in a minute.</p>}
        </div>
      )}
      {data && mode === "approve" && (
        <div className="space-y-3 text-sm text-ink-700">
          <p>A verified doctor account will be created for <b>{data.email}</b>, and they&apos;ll get a link to set their password (valid 48 hours). The photo ID file will be deleted.</p>
          <Field label="Note for the audit log (optional)"><textarea className={inputCls} rows={2} value={text} onChange={(e) => setText(e.target.value)} placeholder="e.g. Found on NMC register, name and council match" /></Field>
        </div>
      )}
      {data && mode === "reject" && (
        <Field label="Reason (emailed to the doctor)" required><textarea className={inputCls} rows={3} value={text} onChange={(e) => setText(e.target.value)} placeholder="e.g. The registration number is not on the NMC register." /></Field>
      )}
      {data && mode === "info" && (
        <div className="space-y-3">
          <p className="text-sm font-semibold text-ink-700">Which documents should they upload again?</p>
          {data.documents.filter((d) => !d.superseded).map((d) => (
            <label key={d.kind} className="flex items-center gap-2 text-sm text-ink-800">
              <input type="checkbox" checked={kinds.includes(d.kind)} onChange={() => setKinds((k) => (k.includes(d.kind) ? k.filter((x) => x !== d.kind) : [...k, d.kind]))} /> {d.title}
            </label>
          ))}
          <Field label="Message (emailed to the doctor)" required><textarea className={inputCls} rows={3} value={text} onChange={(e) => setText(e.target.value)} placeholder="e.g. The scan is too blurry to read the registration number." /></Field>
        </div>
      )}
    </Modal>
  );
}
