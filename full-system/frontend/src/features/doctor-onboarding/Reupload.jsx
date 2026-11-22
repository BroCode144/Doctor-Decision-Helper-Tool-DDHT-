import { useState } from "react";
import { CheckCircle2, Upload } from "lucide-react";
import { api } from "../../lib/api";
import { useApi } from "../../hooks/useApi";
import { Button, ErrorState, Loading } from "../../components/ui";
import { postForm, tokenFromHash } from "./api";
import { FileField, PublicShell } from "./parts";

const FIELD = { REGISTRATION: "registration_certificate", DEGREE: "degree_certificate", PHOTO_ID: "photo_id",
  PG_DEGREE: "pg_degree", HOSPITAL_LETTER: "hospital_letter" };

/** From the "we need another document" email: upload only what was asked for. */
export default function Reupload() {
  const [token] = useState(tokenFromHash);
  const info = useApi(() => api.post("/doctor-applications/reupload/info", { token }), [token]);
  const [files, setFiles] = useState({});
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState(null);
  const [done, setDone] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    setBusy(true);
    setErr(null);
    const fd = new FormData();
    fd.append("token", token);
    Object.entries(files).forEach(([kind, file]) => file && fd.append(FIELD[kind], file));
    try {
      await postForm("/doctor-applications/reupload", fd);
      setDone(true);
    } catch (e2) {
      setErr(e2);
    } finally {
      setBusy(false);
    }
  };

  if (done) {
    return <PublicShell title="Thank you"><p className="flex items-center gap-2 rounded-xl bg-green-50 p-3 text-sm font-semibold text-green-800"><CheckCircle2 size={18} /> Your documents were received and are being checked. We&apos;ll email you.</p></PublicShell>;
  }
  return (
    <PublicShell title="Upload the requested documents" subtitle={info.data ? `Application ${info.data.reference}` : undefined}>
      {info.loading && <Loading />}
      <ErrorState error={info.error} />
      {info.data && (
        <form onSubmit={submit} className="space-y-3">
          {info.data.message && <p className="rounded-xl bg-amber-50 p-3 text-sm text-amber-900">{info.data.message}</p>}
          {info.data.kinds.map((k) => (
            <FileField key={k.kind} label={k.title} required file={files[k.kind]} onChange={(file) => setFiles((s) => ({ ...s, [k.kind]: file }))} />
          ))}
          <ErrorState error={err} />
          <Button type="submit" icon={Upload} loading={busy} disabled={info.data.kinds.some((k) => !files[k.kind])} className="w-full">Upload</Button>
        </form>
      )}
    </PublicShell>
  );
}
