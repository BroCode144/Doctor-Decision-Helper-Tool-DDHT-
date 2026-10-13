import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Stethoscope, Eye, EyeOff, LogIn } from "lucide-react";
import { useAuth } from "../context/AuthContext";
import { useToast } from "../context/ToastContext";
import Button from "../components/ui/Button";
import ErrorMessage from "../components/ui/ErrorMessage";

const DEMO_ACCOUNTS = [
  {
    role: "Doctor",
    email: "doctor@ddht.demo",
    password: "doctor123",
    blurb: "Dr. Raj Mehta — General Physician",
  },
  {
    role: "Patient",
    email: "patient@ddht.demo",
    password: "patient123",
    blurb: "Rahul Sharma — has an authorized doctor",
  },
  {
    role: "Administrator",
    email: "admin@ddht.demo",
    password: "admin123",
    blurb: "Meera Joshi — system administrator",
  },
];

const ROLE_HOME = { doctor: "/doctor", patient: "/patient", admin: "/admin" };

export default function LoginPage() {
  const { login } = useAuth();
  const { showToast } = useToast();
  const navigate = useNavigate();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState("");

  const handleSubmit = (e) => {
    e.preventDefault();
    setError("");

    if (!email || !password) {
      setError("Please enter both an email and a password.");
      return;
    }

    const result = login(email, password);
    if (!result.success) {
      setError(result.error);
      return;
    }

    showToast(`Welcome back, ${result.user.name.split(" ")[0]}.`, "success");
    navigate(ROLE_HOME[result.user.role] || "/", { replace: true });
  };

  const fillDemo = (account) => {
    setEmail(account.email);
    setPassword(account.password);
    setError("");
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-gradient-to-br from-brand-950 via-ink-950 to-ink-900 px-4 py-10">
      <div className="grid w-full max-w-5xl grid-cols-1 overflow-hidden rounded-3xl bg-white shadow-2xl lg:grid-cols-2">
        {/* Brand / info panel */}
        <div className="hidden flex-col justify-between bg-gradient-to-br from-brand-700 to-brand-900 p-10 text-white lg:flex">
          <div>
            <div className="flex items-center gap-2.5">
              <div className="rounded-xl bg-white/15 p-2.5">
                <Stethoscope size={24} />
              </div>
              <span className="font-display text-xl font-bold">DDHT</span>
            </div>
            <h2 className="mt-10 font-display text-3xl font-bold leading-tight">
              Doctor Decision Helper Tool
            </h2>
            <p className="mt-4 max-w-sm text-brand-100">
              A centralized platform for patients to manage their medical records and
              for authorized doctors to access relevant patient history — nothing more,
              nothing less.
            </p>
          </div>
          <div className="space-y-3 rounded-2xl bg-white/10 p-4 text-sm text-brand-50">
            <p className="font-semibold">Core access rule</p>
            <p className="text-brand-100">
              A doctor can only view a patient's records if the patient was previously
              treated by that doctor <strong>and</strong> has explicitly authorized
              access.
            </p>
          </div>
          <p className="text-xs text-brand-200">
            DDHT Prototype — Academic Demonstration Only. AI is intentionally excluded.
          </p>
        </div>

        {/* Login form panel */}
        <div className="flex flex-col justify-center p-8 sm:p-10">
          <div className="mb-6 flex items-center gap-2.5 lg:hidden">
            <div className="rounded-xl bg-brand-600 p-2 text-white">
              <Stethoscope size={20} />
            </div>
            <span className="font-display text-lg font-bold text-ink-900">DDHT</span>
          </div>

          <h1 className="font-display text-2xl font-bold text-ink-900">Sign in</h1>
          <p className="mt-1 text-sm text-ink-500">
            Access your DDHT dashboard as a patient, doctor, or administrator.
          </p>

          <form onSubmit={handleSubmit} className="mt-6 space-y-4" noValidate>
            {error && <ErrorMessage message={error} />}

            <div>
              <label htmlFor="email" className="mb-1.5 block text-sm font-medium text-ink-700">
                Email address
              </label>
              <input
                id="email"
                type="email"
                autoComplete="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="you@ddht.demo"
                className="w-full rounded-xl border border-ink-200 px-4 py-2.5 text-sm focus:border-brand-400 focus:outline-none focus:ring-2 focus:ring-brand-100"
              />
            </div>

            <div>
              <label htmlFor="password" className="mb-1.5 block text-sm font-medium text-ink-700">
                Password
              </label>
              <div className="relative">
                <input
                  id="password"
                  type={showPassword ? "text" : "password"}
                  autoComplete="current-password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••"
                  className="w-full rounded-xl border border-ink-200 px-4 py-2.5 pr-11 text-sm focus:border-brand-400 focus:outline-none focus:ring-2 focus:ring-brand-100"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword((s) => !s)}
                  aria-label={showPassword ? "Hide password" : "Show password"}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-ink-400 hover:text-ink-600"
                >
                  {showPassword ? <EyeOff size={17} /> : <Eye size={17} />}
                </button>
              </div>
            </div>

            <Button type="submit" icon={LogIn} className="w-full">
              Sign in
            </Button>
          </form>

          <div className="mt-8">
            <p className="text-xs font-semibold uppercase tracking-wide text-ink-400">
              Demo accounts — one click to fill
            </p>
            <div className="mt-3 space-y-2">
              {DEMO_ACCOUNTS.map((account) => (
                <button
                  key={account.email}
                  type="button"
                  onClick={() => fillDemo(account)}
                  className="flex w-full items-center justify-between rounded-xl border border-ink-100 bg-ink-50/60 px-4 py-2.5 text-left text-sm transition-colors hover:border-brand-200 hover:bg-brand-50/50"
                >
                  <span>
                    <span className="font-semibold text-ink-800">{account.role}</span>
                    <span className="block text-xs text-ink-400">{account.blurb}</span>
                  </span>
                  <span className="text-xs font-mono text-ink-400">{account.email}</span>
                </button>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
