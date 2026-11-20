import { useState } from "react";
import { Link } from "react-router-dom";
import { Search } from "lucide-react";
import { api } from "../../lib/api";
import { Button, ErrorState, Field, StatusBadge, inputCls } from "../../components/ui";
import { formatDateTime } from "../../lib/format";
import { STATUS_LABEL } from "./api";
import { PublicShell } from "./parts";

/** Public page: reference + email -> where the application is. */
export default function ApplicationStatus() {
  const [ref, setRef] = useState("");
  const [email, setEmail] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState(null);
  const [res, setRes] = useState(null);

  const check = async (e) => {
    e.preventDefault();
    setBusy(true);
    setErr(null);
    setRes(null);
    try {
      setRes(await api.get("/doctor-applications/status", { reference: ref.trim(), email: email.trim() }));
    } catch (e2) {
      setErr(e2);
    } finally {
      setBusy(false);
    }
  };

  const s = res && (STATUS_LABEL[res.status] || { label: res.status, variant: "neutral" });
  return (
    <PublicShell title="Check application status" subtitle="Use the reference from your confirmation email.">
      <form onSubmit={check} className="space-y-4">
        <Field label="Reference" required><input className={inputCls} value={ref} onChange={(e) => setRef(e.target.value)} placeholder="DR-1A2B3C4D" required /></Field>
        <Field label="Email" required><input type="email" className={inputCls} value={email} onChange={(e) => setEmail(e.target.value)} required /></Field>
        <ErrorState error={err} />
        <Button type="submit" icon={Search} loading={busy} className="w-full">Check</Button>
      </form>
      {res && (
        <div className="mt-6 space-y-2 rounded-xl border border-ink-100 p-4 text-sm">
          <div className="flex items-center justify-between gap-2"><span className="font-semibold text-ink-900">{res.reference}</span><StatusBadge variant={s.variant}>{s.label}</StatusBadge></div>
          <p className="text-ink-700">{res.message}</p>
          <p className="text-xs text-ink-400">Submitted {formatDateTime(res.submitted_at)} · last update {formatDateTime(res.updated_at)}</p>
        </div>
      )}
      <p className="mt-6 text-center text-sm text-ink-500"><Link to="/doctor/apply" className="font-semibold text-brand-700 hover:underline">New application</Link> · <Link to="/login" className="font-semibold text-brand-700 hover:underline">Sign in</Link></p>
    </PublicShell>
  );
}
