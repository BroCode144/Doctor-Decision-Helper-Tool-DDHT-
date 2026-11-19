import { useEffect, useState } from "react";
import { KeyRound, MailCheck, Send } from "lucide-react";
import { useToast } from "../../context/contexts";
import { api } from "../../lib/api";
import { Button, ErrorState, Field, inputCls } from "../../components/ui";

/**
 * Forgot password: 1) the user enters their email and we send a 6-digit code to it; 2) they type the code and a new
 * password. The server answers the same way whether or not the email has an account, and signs out old sessions.
 */
export default function ForgotPassword({ initialEmail = "", onDone, onBack }) {
  const { showToast } = useToast();
  const [email, setEmail] = useState(initialEmail);
  const [sent, setSent] = useState(null); // null = not asked yet; else {emailSent}
  const [code, setCode] = useState("");
  const [pw, setPw] = useState("");
  const [pw2, setPw2] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const [wait, setWait] = useState(0);

  useEffect(() => {
    if (wait <= 0) return undefined;
    const t = setTimeout(() => setWait((w) => w - 1), 1000);
    return () => clearTimeout(t);
  }, [wait]);

  const ask = async (e) => {
    e?.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const r = await api.post("/auth/forgot-password", { email: email.trim() });
      setSent({ emailSent: r.email_sent });
      setWait(60);
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  };

  const strong = pw.length >= 8 && /\d/.test(pw) && /[a-z]/i.test(pw);
  const reset = async (e) => {
    e.preventDefault();
    if (!strong) return setError({ message: "Use at least 8 characters with letters and numbers." });
    if (pw !== pw2) return setError({ message: "The two passwords don't match." });
    setBusy(true);
    setError(null);
    try {
      await api.post("/auth/reset-password", { email: email.trim(), code, password: pw });
      showToast("Password changed. Please sign in with your new password.", "success");
      onDone(email.trim());
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
    return undefined;
  };

  if (!sent) {
    return (
      <form onSubmit={ask} className="space-y-4">
        <p className="text-sm text-ink-600">Enter the email you use for DDHT. We&apos;ll send a 6-digit code to it.</p>
        <Field label="Email" required>
          <input type="email" className={inputCls} value={email} onChange={(e) => setEmail(e.target.value)} required autoFocus autoComplete="username" />
        </Field>
        <ErrorState error={error} />
        <Button type="submit" icon={Send} loading={busy} className="w-full">Send me a code</Button>
        <button type="button" onClick={onBack} className="text-sm font-semibold text-ink-500 hover:text-ink-800">Back to sign in</button>
      </form>
    );
  }

  return (
    <form onSubmit={reset} className="space-y-4">
      <div className="flex items-start gap-3 rounded-2xl border border-sky-200 bg-sky-50 p-4 text-sm text-sky-900">
        <MailCheck size={20} className="mt-0.5 shrink-0" />
        <div>
          <p className="font-semibold">Check your email</p>
          <p>If <span className="font-semibold">{email.trim()}</span> has an account, we sent a 6-digit code to it. It expires in 10 minutes.
            {sent.emailSent === false ? "" : " Check your spam folder if you can't see it."}</p>
        </div>
      </div>
      {sent.emailSent === false && (
        <p className="rounded-xl bg-amber-50 p-3 text-xs text-amber-800">
          Email sending isn&apos;t set up on this server yet, so the code was written to the backend log instead (development only).
        </p>
      )}
      <Field label="6-digit code" required>
        <input className={`${inputCls} text-center font-mono text-2xl tracking-[0.5em]`} value={code} required autoFocus
          inputMode="numeric" autoComplete="one-time-code" maxLength={6} pattern="[0-9]{6}"
          onChange={(e) => setCode(e.target.value.replace(/\D/g, "").slice(0, 6))} />
      </Field>
      <Field label="New password" required hint="At least 8 characters, with letters and numbers.">
        <input type="password" className={inputCls} value={pw} onChange={(e) => setPw(e.target.value)} required autoComplete="new-password" />
      </Field>
      <Field label="New password again" required>
        <input type="password" className={inputCls} value={pw2} onChange={(e) => setPw2(e.target.value)} required autoComplete="new-password" />
      </Field>
      <ErrorState error={error} />
      <Button type="submit" icon={KeyRound} loading={busy} disabled={code.length !== 6 || !pw || !pw2} className="w-full">Change password</Button>
      <div className="flex items-center justify-between text-sm">
        <button type="button" onClick={onBack} className="font-semibold text-ink-500 hover:text-ink-800">Back to sign in</button>
        <button type="button" onClick={() => ask()} disabled={wait > 0 || busy}
          className="font-semibold text-brand-700 hover:text-brand-900 disabled:cursor-not-allowed disabled:text-ink-400">
          {wait > 0 ? `Send a new code in ${wait}s` : "Send a new code"}
        </button>
      </div>
    </form>
  );
}
