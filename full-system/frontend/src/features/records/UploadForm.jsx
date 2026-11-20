import { useRef, useState } from "react";
import { CheckCircle2, FileUp, UploadCloud, X } from "lucide-react";
import { uploadDocument } from "../../lib/api";
import { formatBytes, RECORD_TYPES, todayISO } from "../../lib/format";
import { useToast } from "../../context/contexts";
import { AutoBadge, Button, ErrorState, Field, Select, inputCls } from "../../components/ui";
import { ContentCheck } from "./ContentCheck";

const ACCEPT = ".pdf,.png,.jpg,.jpeg,application/pdf,image/png,image/jpeg";
const MAX_MB = 10;

/**
 * Real upload form for all roles. The backend decides whether the upload is
 * allowed (patient: own record only; doctor: patient consent;
 * admin: explicit permission + justification for patient documents).
 *
 * mode: "patient" | "doctor" | "admin"
 */
export default function UploadForm({ mode, patientId, patientOptions = [], onUploaded }) {
  const { showToast } = useToast();
  const fileRef = useRef(null);
  const [file, setFile] = useState(null);
  const [form, setForm] = useState({
    document_type: "LAB_REPORT",
    document_date: todayISO(),
    title: "",
    description: "",
    category: mode === "admin" ? "ADMINISTRATIVE" : "MEDICAL",
    patient_id: patientId || "",
    admin_reason: "",
  });
  const [progress, setProgress] = useState(0);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const [result, setResult] = useState(null);

  const set = (k) => (v) => setForm((f) => ({ ...f, [k]: v?.target ? v.target.value : v }));
  const adminPatientDoc = mode === "admin" && form.category === "MEDICAL";

  const pickFile = (f) => {
    setError(null);
    setResult(null);
    if (!f) return setFile(null);
    if (f.size > MAX_MB * 1024 * 1024) {
      setError({ message: `File is too large. Maximum size is ${MAX_MB} MB.` });
      return setFile(null);
    }
    setFile(f);
    if (!form.title) setForm((s) => ({ ...s, title: f.name.replace(/\.[^.]+$/, "") }));
  };
  // The X on the box: forget the chosen file (and the title, if it was filled in from the file name).
  const removeFile = () => {
    const auto = file ? file.name.replace(/\.[^.]+$/, "") : null;
    setFile(null);
    setError(null);
    setResult(null);
    if (fileRef.current) fileRef.current.value = "";
    if (auto && form.title === auto) setForm((s) => ({ ...s, title: "" }));
  };

  const submit = async (e) => {
    e.preventDefault();
    if (!file) return setError({ message: "Choose a file to upload." });
    if ((mode === "doctor" || adminPatientDoc) && !form.patient_id) return setError({ message: "Select a patient." });
    const fd = new FormData();
    fd.append("file", file);
    fd.append("document_type", form.document_type);
    fd.append("document_date", form.document_date);
    fd.append("title", form.title);
    fd.append("description", form.description);
    fd.append("category", form.category);
    if (mode !== "patient" && form.patient_id && form.category === "MEDICAL") fd.append("patient_id", form.patient_id);
    if (adminPatientDoc) fd.append("admin_reason", form.admin_reason);
    setBusy(true);
    setError(null);
    setResult(null);
    setProgress(0);
    try {
      const res = await uploadDocument(fd, setProgress);
      setResult(res);
      showToast("Document uploaded and processed.", "success");
      setFile(null);
      if (fileRef.current) fileRef.current.value = "";
      setForm((f) => ({ ...f, title: "", description: "", admin_reason: "" }));
      onUploaded?.(res.document);
    } catch (err) {
      setError(err);
      showToast(err.reason || err.message, "error");
    } finally {
      setBusy(false);
    }
  };

  return (
    <form onSubmit={submit} className="space-y-5" noValidate>
      {mode === "admin" && (
        <Field label="Document category" required>
          <Select value={form.category} onChange={set("category")} options={[
            { value: "ADMINISTRATIVE", label: "Administrative / system document (no patient)" },
            { value: "MEDICAL", label: "Patient medical document (requires permission + justification)" },
          ]} />
        </Field>
      )}

      {(mode === "doctor" || adminPatientDoc) && !patientId && (
        <Field label="Patient" required hint={mode === "doctor" ? "Only patients you have treated AND who authorized you are accepted by the server." : undefined}>
          <Select value={form.patient_id} onChange={set("patient_id")} placeholder="Select patient…" options={patientOptions} />
        </Field>
      )}

      <div
        className={`relative rounded-2xl border-2 border-dashed p-6 text-center ${file ? "border-brand-300 bg-brand-50/40" : "border-ink-200 bg-ink-50/50"}`}
        onDragOver={(e) => e.preventDefault()}
        onDrop={(e) => {
          e.preventDefault();
          pickFile(e.dataTransfer.files?.[0]);
        }}
      >
        {file && (
          <button type="button" onClick={removeFile} disabled={busy} aria-label={`Remove ${file.name}`} title="Remove this file"
            className="absolute top-3 right-3 rounded-full border border-ink-200 bg-white p-1.5 text-ink-500 shadow-sm hover:border-red-200 hover:bg-red-50 hover:text-red-600 disabled:opacity-50">
            <X size={16} />
          </button>
        )}
        <UploadCloud className="mx-auto text-brand-600" size={32} />
        <p className="mt-2 text-sm font-semibold text-ink-800">{file ? file.name : "Drag a file here or choose one"}</p>
        <p className="text-xs text-ink-500">{file ? formatBytes(file.size) : mode === "patient"
          ? `Medical files only: lab or test reports, prescriptions, discharge summaries, scan reports, medical certificates. PDF, PNG or JPEG · max ${MAX_MB} MB. Other files (bills, tickets, CVs...) are refused.`
          : `Supported: PDF (text is extracted for search/AI), PNG, JPEG · max ${MAX_MB} MB`}</p>
        <label className="mt-3 inline-flex cursor-pointer items-center gap-2 rounded-xl border border-ink-200 bg-white px-4 py-2 text-sm font-semibold text-ink-700 hover:bg-ink-50">
          <FileUp size={16} /> Choose file
          <input ref={fileRef} type="file" accept={ACCEPT} className="sr-only" onChange={(e) => pickFile(e.target.files?.[0])} />
        </label>
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        <Field label="Record / document type" required>
          <Select value={form.document_type} onChange={set("document_type")} options={RECORD_TYPES} />
        </Field>
        <Field label="Document date" required>
          <input type="date" className={inputCls} value={form.document_date} max={todayISO()} onChange={set("document_date")} required />
        </Field>
      </div>
      <Field label="Title">
        <input className={inputCls} value={form.title} onChange={set("title")} maxLength={250} placeholder="e.g. Lipid profile — September 2026" />
      </Field>
      <Field label="Description / notes">
        <textarea className={inputCls} rows={3} value={form.description} onChange={set("description")} maxLength={5000} />
      </Field>
      {adminPatientDoc && (
        <Field label="Administrative justification" required hint="Recorded in the audit log. At least 10 characters.">
          <textarea className={inputCls} rows={2} value={form.admin_reason} onChange={set("admin_reason")} maxLength={1000}
            placeholder="e.g. Paper report delivered to the records office by the patient" />
        </Field>
      )}

      {busy && (
        <div aria-live="polite">
          <div className="h-2 overflow-hidden rounded-full bg-ink-100">
            <div className="h-full bg-brand-500 transition-all" style={{ width: `${progress}%` }} />
          </div>
          <p className="mt-1 text-xs text-ink-500">{progress < 100 ? `Uploading… ${progress}%` : "Processing: extracting text, chunking, embedding…"}</p>
        </div>
      )}

      <ErrorState error={error} />

      {result && (
        <div role="status" className="rounded-2xl border border-green-200 bg-green-50 p-4 text-sm">
          <p className="flex items-center gap-2 font-semibold text-green-800"><CheckCircle2 size={18} /> Uploaded: {result.document.title} ({result.document.id})</p>
          <div className="mt-2 flex flex-wrap gap-2">
            <AutoBadge value={result.document.processing_status} />
            <AutoBadge value={result.document.extraction_status} />
            <AutoBadge value={result.document.index_status} />
            <ContentCheck doc={result.document} />
          </div>
          <p className="mt-2 text-ink-700">{result.message}</p>
          {result.document.chunk_count > 0 && <p className="text-xs text-ink-500">{result.document.chunk_count} text chunk(s) indexed for AI retrieval.</p>}
        </div>
      )}

      <div className="flex justify-end">
        <Button type="submit" icon={UploadCloud} loading={busy} disabled={!file}>Upload Document</Button>
      </div>
    </form>
  );
}
