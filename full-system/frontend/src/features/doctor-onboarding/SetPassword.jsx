import { useState } from "react";
import { Link } from "react-router-dom";
import { CheckCircle2, KeyRound, MailPlus } from "lucide-react";
import { api } from "../../lib/api";
import { Button, ErrorState, Field, inputCls } from "../../components/ui";
import { tokenFromHash } from "./api";
import { PublicShell } from "./parts";

/** From the approval email: choose a password (link valid 48 hours, works once). Expired -> ask for a new link. */
export default function SetPassword() {
  const [token] = useState(tokenFromHash);
  const [pw, setPw] = useState("");
  const [pw2, setPw2] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState(null);
  const [done, setDone] = useState(null);
  const [email, setEmail] = useState("");
  const [sent, setSent] = useState("");

  const save = async (e) => {
    e.preventDefault();
    if (pw !== pw2) return setErr({ message: "The two passwords don't match." });
    setBusy(true);
    setErr(null);
    try {
      setDone(await api.post("/auth/set-password", { token, password: pw }));
    } catch (e2) {
      setErr(e2);
    } finally {
      setBusy(false);
    }
    return undefined;
  };
  const newLink = async (e) => {
    e.preventDefault();
    setBusy(true);
    try {
      setSent((await api.post("/auth/set-password/new-link", { email: email.trim() })).message);
    } catch (e2) {
      setErr(e2);
    } finally {
      setBusy(false);
    }
  };

  if (done) {
    return (
      <PublicShell title="Password saved">
        <p className="flex items-center gap-2 rounded-xl bg-green-50 p-3 text-sm font-semibold text-green-800"><CheckCircle2 size={18} /> You can sign in now as {done.email}.</p>
        <Link to="/login" className="mt-4 inline-block font-semibold text-brand-700 hover:underline">Go to sign in</Link>
      </PublicShell>
    );
  }
  const expired = err?.code === "LINK_EXPIRED" || err?.code === "LINK_INVALID" || !token;
  return (
    <PublicShell title="Choose your password" subtitle="Your DDHT doctor account has been approved.">
      {!expired && (
        <form onSubmit={save} className="space-y-4">
          <Field label="New password" required hint="At least 8 characters with letters and numbers.">
            <input type="password" className={inputCls} value={pw} onChange={(e) => setPw(e.target.value)} required minLength={8} autoComplete="new-password" />
          </Field>
          <Field label="Repeat password" required><input type="password" className={inputCls} value={pw2} onChange={(e) => setPw2(e.target.value)} required autoComplete="new-password" /></Field>
          <ErrorState error={err} />
          <Button type="submit" icon={KeyRound} loading={busy} className="w-full">Save password</Button>
        </form>
      )}
      {expired && (
        <form onSubmit={newLink} className="space-y-4">
          <p className="rounded-xl bg-amber-50 p-3 text-sm text-amber-900">{token ? err?.message : "This link is incomplete."} Enter your email to get a new link.</p>
          <Field label="Email" required><input type="email" className={inputCls} value={email} onChange={(e) => setEmail(e.target.value)} required /></Field>
          {sent && <p className="text-sm text-green-800">{sent}</p>}
          <Button type="submit" icon={MailPlus} loading={busy} className="w-full">Send a new link</Button>
        </form>
      )}
    </PublicShell>
  );
}
