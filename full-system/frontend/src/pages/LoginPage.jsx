import { useEffect, useState } from "react";
import { Link, Navigate, useNavigate } from "react-router-dom";
import { CalendarCheck, FileText, LogIn, MailCheck, ShieldCheck, Sparkles, Stethoscope, UserPlus } from "lucide-react";
import { useAuth, useToast } from "../context/contexts";
import { api } from "../lib/api";
import { ROLE_HOME } from "../components/layout/navConfig";
import { Button, ErrorState, Field, Tabs, inputCls } from "../components/ui";
import ForgotPassword from "../features/auth/ForgotPassword";
import { MovingBackground } from "../features/auth/DotField";

/** One message in the sign-in page's sample chat with the AI assistant (appears once, in turn). */
function Bubble({ from, delay, children }) {
  const ai = from === "ai";
  return (
    <div className={`animate-rise-in flex ${ai ? "justify-start" : "justify-end"}`} style={{ "--delay": `${delay}ms` }}>
      <p className={`max-w-[85%] rounded-2xl px-3.5 py-2 text-sm leading-relaxed ${ai
        ? "rounded-bl-md bg-white/95 text-slate-800 shadow-sm"
        : "rounded-br-md bg-brand-500 text-white"}`}>
        {children}
      </p>
    </div>
  );
}

const FEATURES = [
  { icon: Sparkles, text: "Chat to book" },
  { icon: FileText, text: "All your reports" },
  { icon: ShieldCheck, text: "You control access" },
];

const DEMO = [
  { role: "Doctor", email: "doctor@ddht.demo", password: "doctor123", who: "Dr. Raj Mehta (D001)" },
  { role: "Patient", email: "patient@ddht.demo", password: "patient123", who: "Rahul Sharma (P001)" },
  { role: "Admin", email: "admin@ddht.demo", password: "admin123", who: "Meera Joshi (A001)" },
  { role: "Reception", email: "reception@ddht.demo", password: "reception123", who: "Pooja Nair (check-in only)" },
];

/**
 * "Check your email": the patient types the 6-digit code sent at sign-up. Success signs them in.
 * emailSent=false means email isn't set up on this server (development): the code is in the backend log.
 */
function VerifyEmail({ email, emailSent, onBack }) {
  const { startSession } = useAuth();
  const { showToast } = useToast();
  const navigate = useNavigate();
  const [code, setCode] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const [wait, setWait] = useState(60);
  const [sentInfo, setSentInfo] = useState(emailSent);

  useEffect(() => {
    if (wait <= 0) return undefined;
    const t = setTimeout(() => setWait((w) => w - 1), 1000);
    return () => clearTimeout(t);
  }, [wait]);

  const submit = async (e) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const u = startSession(await api.post("/auth/verify-email", { email, code: code.trim() }));
      showToast("Email confirmed. Welcome!", "success");
      navigate(ROLE_HOME[u.role], { replace: true });
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  };
  const resend = async () => {
    setError(null);
    try {
      const r = await api.post("/auth/resend-code", { email });
      setSentInfo(r.email_sent);
      setWait(60);
      showToast("If a new code was due, it's on its way. Use the latest email.", "success");
    } catch (err) {
      setError(err);
    }
  };

  return (
    <form onSubmit={submit} className="space-y-4">
      <div className="flex items-start gap-3 rounded-2xl border border-sky-200 bg-sky-50 p-4 text-sm text-sky-900">
        <MailCheck size={20} className="mt-0.5 shrink-0" />
        <div>
          <p className="font-semibold">Check your email</p>
          <p>{sentInfo === false ? "We made" : "We sent"} a 6-digit code for <span className="font-semibold">{email}</span>. It expires in 10 minutes.{sentInfo === false ? "" : " Check your spam folder if you can't see it."}</p>
        </div>
      </div>
      {sentInfo === false && (
        <p className="rounded-xl bg-amber-50 p-3 text-xs text-amber-800">
          Email sending isn&apos;t set up on this server yet, so the code was written to the backend log instead (development only).
        </p>
      )}
      <Field label="6-digit code" required>
        <input className={`${inputCls} text-center font-mono text-2xl tracking-[0.5em]`} value={code} required autoFocus
          inputMode="numeric" autoComplete="one-time-code" maxLength={6} pattern="[0-9]{6}"
          onChange={(e) => setCode(e.target.value.replace(/\D/g, "").slice(0, 6))} />
      </Field>
      <ErrorState error={error} />
      <Button type="submit" icon={MailCheck} loading={busy} disabled={code.length !== 6} className="w-full">Confirm and sign in</Button>
      <div className="flex items-center justify-between text-sm">
        <button type="button" onClick={onBack} className="font-semibold text-ink-500 hover:text-ink-800">Back</button>
        <button type="button" onClick={resend} disabled={wait > 0}
          className="font-semibold text-brand-700 hover:text-brand-900 disabled:cursor-not-allowed disabled:text-ink-400">
          {wait > 0 ? `Send a new code in ${wait}s` : "Send a new code"}
        </button>
      </div>
    </form>
  );
}

function RegisterForm({ onVerify }) {
  const { showToast } = useToast();
  const { login } = useAuth();
  const navigate = useNavigate();
  const [f, setF] = useState({ role: "PATIENT", full_name: "", email: "", password: "", specialization: "", license_number: "" });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const set = (k) => (e) => setF((s) => ({ ...s, [k]: e?.target ? e.target.value : e }));
  const submit = async (e) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const body = { ...f };
      if (f.role === "PATIENT") {
        delete body.specialization;
        delete body.license_number;
      }
      const res = await api.post("/auth/register", body);
      showToast(res.message, "success");
      if (res.needs_verification) {
        onVerify({ email: res.email, emailSent: res.email_sent });
        return;
      }
      const u = await login(f.email.trim(), f.password);
      navigate(ROLE_HOME[u.role], { replace: true });
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  };
  return (
    <form onSubmit={submit} className="space-y-4">
      <p className="rounded-xl bg-sky-50 p-3 text-sm text-sky-900">
        This creates a patient account. Doctor? <Link to="/doctor/apply" className="font-semibold underline">Apply here</Link> with your registration documents.
      </p>
      <Field label="Full name" required><input className={inputCls} value={f.full_name} onChange={set("full_name")} required /></Field>
      <Field label="Email" required><input type="email" className={inputCls} value={f.email} onChange={set("email")} required autoComplete="email" /></Field>
      <Field label="Password" required hint="At least 8 characters with letters and numbers.">
        <input type="password" className={inputCls} value={f.password} onChange={set("password")} required autoComplete="new-password" />
      </Field>
      <ErrorState error={error} />
      <Button type="submit" icon={UserPlus} loading={busy} className="w-full">Create account</Button>
    </form>
  );
}

export default function LoginPage() {
  const { user, login } = useAuth();
  const navigate = useNavigate();
  const [tab, setTab] = useState("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const [verify, setVerify] = useState(null); // {email, emailSent} while waiting for the emailed code
  const [forgot, setForgot] = useState(false);

  if (user) return <Navigate to={ROLE_HOME[user.role]} replace />;

  const submit = async (e) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const u = await login(email.trim(), password);
      navigate(ROLE_HOME[u.role], { replace: true });
    } catch (err) {
      if (err.code === "EMAIL_NOT_VERIFIED") setVerify({ email: err.detail.email, emailSent: err.detail.email_sent });
      else setError(err);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="relative flex min-h-screen items-center justify-center overflow-hidden bg-[#0b1430] px-4 py-10">
      <MovingBackground />
      <div className="relative grid w-full max-w-6xl items-center gap-10 lg:grid-cols-[1.1fr_1fr] lg:gap-14">
        {/* Left: who we are, the slogan and a short sample chat with the AI assistant */}
        <div className="text-white">
          <div className="animate-rise-in flex items-center gap-2.5">
            <span className="rounded-xl bg-white/10 p-2 ring-1 ring-white/20 backdrop-blur"><Stethoscope size={20} /></span>
            <p className="font-display text-lg font-bold tracking-wide">DDHT</p>
          </div>
          <p className="animate-rise-in mt-8 inline-flex items-center gap-1.5 rounded-full bg-white/10 px-3 py-1 text-xs font-semibold text-cyan-200 ring-1 ring-white/15" style={{ "--delay": "80ms" }}>
            <Sparkles size={13} /> AI health assistant
          </p>
          <h1 className="animate-rise-in mt-4 font-display text-4xl leading-tight font-bold sm:text-5xl" style={{ "--delay": "140ms" }}>
            Healthcare that<br />
            <span className="bg-gradient-to-r from-cyan-300 via-sky-300 to-violet-300 bg-clip-text text-transparent">listens first.</span>
          </h1>
          <p className="animate-rise-in mt-4 max-w-md text-base text-slate-300" style={{ "--delay": "200ms" }}>
            Tell our assistant how you feel. It books your visit and gets your doctor ready before you walk in.
          </p>

          {/* sample chat (desktop only) */}
          <div className="animate-rise-in mt-8 hidden max-w-md rounded-3xl border border-white/10 bg-white/5 p-4 shadow-2xl backdrop-blur-md lg:block" style={{ "--delay": "300ms" }}>
            <div className="mb-3 flex items-center gap-2 border-b border-white/10 pb-3">
              <span className="relative rounded-full bg-gradient-to-br from-cyan-400 to-brand-500 p-1.5"><Sparkles size={14} /></span>
              <p className="text-sm font-semibold">DDHT Assistant</p>
              <span className="ml-auto flex items-center gap-1 text-xs text-emerald-300"><span className="h-1.5 w-1.5 rounded-full bg-emerald-400" />online</span>
            </div>
            <div className="space-y-2.5">
              <Bubble from="ai" delay={700}>Hi! What&apos;s bothering you today?</Bubble>
              <Bubble from="me" delay={1500}>Headache and fever since Monday.</Bubble>
              <Bubble from="ai" delay={2300}>Sorry to hear that. A few quick questions, then I&apos;ll find you a slot.</Bubble>
              <div className="animate-rise-in flex items-center gap-2" style={{ "--delay": "3100ms" }}>
                <span className="flex items-center gap-2 rounded-2xl rounded-bl-md bg-emerald-400/15 px-3.5 py-2 text-sm text-emerald-200 ring-1 ring-emerald-300/20">
                  <CalendarCheck size={15} /> Visit booked
                </span>
                <span className="flex gap-1 rounded-2xl bg-white/10 px-3 py-3">
                  {[0, 150, 300].map((d) => <span key={d} className="typing-dot h-1.5 w-1.5 rounded-full bg-white/70" style={{ animationDelay: `${d}ms` }} />)}
                </span>
              </div>
            </div>
          </div>

          <div className="animate-rise-in mt-6 hidden flex-wrap gap-2 lg:flex" style={{ "--delay": "400ms" }}>
            {FEATURES.map(({ icon: Icon, text }) => (
              <span key={text} className="inline-flex items-center gap-1.5 rounded-full bg-white/5 px-3 py-1.5 text-xs text-slate-200 ring-1 ring-white/10">
                <Icon size={13} className="text-cyan-300" /> {text}
              </span>
            ))}
          </div>
        </div>

        {/* Right: the sign-in card */}
        <div className="animate-rise-in w-full rounded-3xl bg-white p-8 shadow-[0_30px_80px_-20px_rgba(0,0,0,0.55)] ring-1 ring-white/20 sm:p-10" style={{ "--delay": "150ms" }}>
          {verify ? (
            <>
              <h2 className="font-display text-2xl font-bold text-ink-900">Confirm your email</h2>
              <div className="mt-6"><VerifyEmail key={verify.email} email={verify.email} emailSent={verify.emailSent} onBack={() => { setVerify(null); setTab("login"); }} /></div>
            </>
          ) : forgot ? (
            <>
              <h2 className="font-display text-2xl font-bold text-ink-900">Reset your password</h2>
              <div className="mt-6">
                <ForgotPassword initialEmail={email} onBack={() => setForgot(false)}
                  onDone={(e) => { setForgot(false); setTab("login"); setEmail(e); setPassword(""); setError(null); }} />
              </div>
            </>
          ) : (<>
          <Tabs tabs={[{ value: "login", label: "Sign in" }, { value: "register", label: "Register" }]} active={tab} onChange={setTab} />
          {tab === "login" ? (
            <div key="login" className="animate-rise-in">
              <h2 className="mt-6 font-display text-2xl font-bold text-ink-900">Sign in</h2>
              <form onSubmit={submit} className="mt-6 space-y-4">
                <Field label="Email"><input type="email" className={inputCls} value={email} onChange={(e) => setEmail(e.target.value)} required autoComplete="username" /></Field>
                <Field label="Password"><input type="password" className={inputCls} value={password} onChange={(e) => setPassword(e.target.value)} required autoComplete="current-password" /></Field>
                <div className="-mt-2 text-right">
                  <button type="button" onClick={() => { setError(null); setForgot(true); }} className="text-sm font-semibold text-brand-700 hover:text-brand-900">Forgot password?</button>
                </div>
                <ErrorState error={error} />
                <Button type="submit" icon={LogIn} loading={busy} className="w-full">Sign in</Button>
              </form>
              <div className="mt-8">
                <p className="text-xs font-semibold tracking-wide text-ink-400 uppercase">Demo accounts (local demo only)</p>
                <div className="mt-2 grid gap-2">
                  {DEMO.map((d) => (
                    <button key={d.email} type="button" onClick={() => { setEmail(d.email); setPassword(d.password); }}
                      className="flex items-center justify-between rounded-xl border border-ink-100 px-3 py-2 text-left text-sm transition duration-200 hover:-translate-y-px hover:border-brand-200 hover:bg-brand-50 hover:shadow-sm">
                      <span><span className="font-semibold text-ink-800">{d.role}</span> <span className="text-ink-500">· {d.who}</span></span>
                      <span className="text-xs text-ink-400">{d.email}</span>
                    </button>
                  ))}
                </div>
              </div>
            </div>
          ) : (
            <div key="register" className="animate-rise-in mt-6">
              <RegisterForm onVerify={setVerify} />
            </div>
          )}
          </>)}
          <p className="mt-6 text-center text-xs text-ink-400">Fictional demo data only. Not for real clinical use.</p>
        </div>
      </div>
    </div>
  );
}
