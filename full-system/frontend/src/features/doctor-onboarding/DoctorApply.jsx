import { useState } from "react";
import { Link } from "react-router-dom";
import { CheckCircle2, Send, ShieldCheck } from "lucide-react";
import { api } from "../../lib/api";
import { useApi } from "../../hooks/useApi";
import { Button, ErrorState, Field, Loading, Select, inputCls } from "../../components/ui";
import { postForm } from "./api";
import { FileField, PublicShell } from "./parts";

const DOCS = [
  { key: "registration_certificate", label: "Medical Council registration certificate", required: true },
  { key: "degree_certificate", label: "MBBS degree certificate", required: true },
  { key: "photo_id", label: "Photo ID", required: true, hint: "Masked Aadhaar (first 8 digits hidden), PAN or passport. Deleted after the decision." },
  { key: "pg_degree", label: "Postgraduate degree (MD / MS / DNB)", specialist: true },
  { key: "hospital_letter", label: "Hospital appointment letter or employee ID", hint: "Recommended if you choose a hospital." },
];
const THIS_YEAR = new Date().getFullYear();
const EMPTY = { full_name: "", email: "", phone: "", specialization: "", qualification: "MBBS", council: "", registration_number: "",
  registration_year: "", claims_specialist: false, hospital_id: "" };

/** Public page: a doctor applies with their details and documents. No account exists until an admin approves. */
export default function DoctorApply() {
  const opts = useApi(() => api.get("/doctor-applications/options"), []);
  const [f, setF] = useState(EMPTY);
  const [files, setFiles] = useState({});
  const [tried, setTried] = useState(false);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState(null);
  const [done, setDone] = useState(null);
  const set = (k) => (v) => setF((s) => ({ ...s, [k]: v?.target ? (v.target.type === "checkbox" ? v.target.checked : v.target.value) : v }));

  const needed = DOCS.filter((d) => d.required || (d.specialist && f.claims_specialist));
  const missingFiles = needed.filter((d) => !files[d.key]).map((d) => d.key);

  const submit = async (e) => {
    e.preventDefault();
    setTried(true);
    if (missingFiles.length) return setErr({ message: "Please attach every required document (highlighted)." });
    setBusy(true);
    setErr(null);
    const fd = new FormData();
    Object.entries(f).forEach(([k, v]) => { if (v !== "" && v !== null) fd.append(k, String(v)); });
    Object.entries(files).forEach(([k, file]) => file && fd.append(k, file));
    try {
      setDone(await postForm("/doctor-applications", fd));
    } catch (e2) {
      setErr(e2);
    } finally {
      setBusy(false);
    }
    return undefined;
  };

  if (done) {
    return (
      <PublicShell title="Application received">
        <div className="space-y-4 text-sm text-ink-700">
          <p className="flex items-center gap-2 rounded-xl bg-green-50 p-3 font-semibold text-green-800"><CheckCircle2 size={18} /> Your reference: {done.reference}</p>
          <p>We&apos;ve emailed you a copy. Your documents are checked automatically first, then by our team, usually within 1-2 working days.</p>
          <p>When you&apos;re approved, we&apos;ll email you a link to choose your password. You can&apos;t sign in before that.</p>
          <Link to="/doctor/application-status" className="font-semibold text-brand-700 hover:underline">Check application status</Link>
        </div>
      </PublicShell>
    );
  }

  return (
    <PublicShell wide title="Join DDHT as a doctor" subtitle="Your details and documents are checked before your account is created.">
      {opts.loading && <Loading />}
      <ErrorState error={opts.error} onRetry={opts.reload} />
      {opts.data && (
        <form onSubmit={submit} className="space-y-6">
          <section className="grid gap-4 sm:grid-cols-2">
            <Field label="Full name (as on your certificates)" required><input className={inputCls} value={f.full_name} onChange={set("full_name")} required minLength={2} placeholder="Dr. Kavita Menon" /></Field>
            <Field label="Email" required hint="We'll send updates and your password link here."><input type="email" className={inputCls} value={f.email} onChange={set("email")} required autoComplete="email" /></Field>
            <Field label="Phone"><input className={inputCls} value={f.phone} onChange={set("phone")} autoComplete="tel" /></Field>
            <Field label="Specialization" required><input className={inputCls} value={f.specialization} onChange={set("specialization")} required placeholder="General Physician" /></Field>
            <Field label="Qualification" required><input className={inputCls} value={f.qualification} onChange={set("qualification")} required placeholder="MBBS, MD (Medicine)" /></Field>
            <Field label="Hospital (optional)">
              <Select value={f.hospital_id} onChange={set("hospital_id")} placeholder="None / independent" options={opts.data.hospitals.map((h) => ({ value: h.id, label: h.name }))} />
            </Field>
          </section>
          <section className="grid gap-4 rounded-2xl bg-ink-50 p-4 sm:grid-cols-3">
            <div className="sm:col-span-3 flex items-center gap-2 text-sm font-semibold text-ink-700"><ShieldCheck size={16} /> Medical registration</div>
            <Field label="Medical council" required><Select value={f.council} onChange={set("council")} placeholder="Choose" options={opts.data.councils} required /></Field>
            <Field label="Registration number" required><input className={inputCls} value={f.registration_number} onChange={set("registration_number")} required pattern="[A-Za-z0-9/\- ]+" /></Field>
            <Field label="Year of registration" required><input type="number" min="1950" max={THIS_YEAR} className={inputCls} value={f.registration_year} onChange={set("registration_year")} required /></Field>
          </section>
          <label className="flex cursor-pointer items-start gap-2.5 text-sm text-ink-700">
            <input type="checkbox" className="mt-0.5" checked={f.claims_specialist} onChange={set("claims_specialist")} />
            <span><span className="font-semibold text-ink-900">I am a specialist</span> (MD / MS / DNB). Then your postgraduate degree is required.</span>
          </label>
          <section className="space-y-2">
            <p className="text-sm font-semibold text-ink-700">Documents</p>
            {DOCS.filter((d) => !d.specialist || f.claims_specialist).map((d) => (
              <FileField key={d.key} label={d.label} hint={d.hint} required={d.required || d.specialist} file={files[d.key]}
                invalid={tried && missingFiles.includes(d.key)} onChange={(file) => setFiles((s) => ({ ...s, [d.key]: file }))} />
            ))}
            <p className="text-xs text-ink-500">Text PDFs are read on our server. Photos or scans of certificates are read by an AI service (Groq) to check the details; your photo ID is never sent to it. An admin also checks your number on the NMC register.</p>
          </section>
          <ErrorState error={err} />
          <Button type="submit" icon={Send} loading={busy} className="w-full">Submit application</Button>
          <p className="text-center text-sm text-ink-500">Already applied? <Link to="/doctor/application-status" className="font-semibold text-brand-700 hover:underline">Check status</Link></p>
        </form>
      )}
    </PublicShell>
  );
}
