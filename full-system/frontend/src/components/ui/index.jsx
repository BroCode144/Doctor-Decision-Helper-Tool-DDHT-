import {
  AlertTriangle,
  CheckCircle2,
  Circle,
  Clock,
  Inbox,
  Loader2,
  Search,
  ShieldX,
  XCircle,
} from "lucide-react";

// ---------------------------------------------------------------------------
const BTN = {
  primary: "bg-brand-600 text-white hover:bg-brand-700 focus-visible:ring-brand-300",
  secondary: "bg-white text-ink-700 border border-ink-200 hover:bg-ink-50 focus-visible:ring-ink-200",
  danger: "bg-red-600 text-white hover:bg-red-700 focus-visible:ring-red-300",
  ghost: "text-ink-600 hover:bg-ink-100 focus-visible:ring-ink-200 shadow-none",
};
const SIZES = { sm: "px-3 py-1.5 text-xs", md: "px-4 py-2.5 text-sm" };

export function Button({ variant = "primary", size = "md", icon: Icon, loading = false, className = "", children, disabled, ...props }) {
  return (
    <button
      type="button"
      disabled={disabled || loading}
      className={`inline-flex shrink-0 items-center justify-center gap-2 whitespace-nowrap rounded-xl font-semibold shadow-sm transition-colors focus-visible:outline-none focus-visible:ring-2 disabled:cursor-not-allowed disabled:opacity-50 ${BTN[variant]} ${SIZES[size]} ${className}`}
      {...props}
    >
      {loading ? <Loader2 size={size === "sm" ? 14 : 16} className="animate-spin" /> : Icon && <Icon size={size === "sm" ? 14 : 16} />}
      {children}
    </button>
  );
}

// ---------------------------------------------------------------------------
const BADGE = {
  success: ["bg-green-50 text-green-700 ring-green-200", CheckCircle2],
  danger: ["bg-red-50 text-red-700 ring-red-200", XCircle],
  warning: ["bg-amber-50 text-amber-700 ring-amber-200", AlertTriangle],
  pending: ["bg-sky-50 text-sky-700 ring-sky-200", Clock],
  neutral: ["bg-ink-100 text-ink-600 ring-ink-200", Circle],
};

/** Status indicator: always icon + text, never color alone. */
export function StatusBadge({ variant = "neutral", children, icon = true }) {
  const [cls, Icon] = BADGE[variant] || BADGE.neutral;
  return (
    <span className={`inline-flex items-center gap-1.5 whitespace-nowrap rounded-full px-2.5 py-1 text-xs font-semibold ring-1 ring-inset ${cls}`}>
      {icon && <Icon size={13} className="shrink-0" />}
      {children}
    </span>
  );
}

const STATUS_VARIANT = {
  ACTIVE: "success", GRANTED: "success", VERIFIED: "success", AUTHORIZED: "success", SUCCESS: "success",
  PROCESSED: "success", EXTRACTED: "success", INDEXED: "success",
  RESTRICTED: "danger", REVOKED: "danger", REJECTED: "danger", DENIED: "danger", FAILURE: "danger", FAILED: "danger",
  PROCESSED_WITH_WARNINGS: "warning", SCANNED_NO_TEXT: "warning", EMPTY: "warning",
  PENDING: "pending", ARCHIVED: "neutral", SKIPPED: "neutral", NOT_APPLICABLE: "neutral", NOT_GRANTED: "neutral",
};
export function AutoBadge({ value }) {
  if (!value) return null;
  return <StatusBadge variant={STATUS_VARIANT[value] || "neutral"}>{value.replaceAll("_", " ").toLowerCase().replace(/^\w/, (c) => c.toUpperCase())}</StatusBadge>;
}

// ---------------------------------------------------------------------------
export function Card({ title, subtitle, actions, children, className = "", padded = true }) {
  return (
    <section className={`rounded-2xl border border-ink-100 bg-white shadow-sm ${className}`}>
      {(title || actions) && (
        <header className="flex flex-wrap items-start justify-between gap-3 border-b border-ink-100 px-5 py-4">
          <div>
            {title && <h2 className="font-display text-base font-bold text-ink-900">{title}</h2>}
            {subtitle && <p className="mt-0.5 text-sm text-ink-500">{subtitle}</p>}
          </div>
          {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
        </header>
      )}
      <div className={padded ? "p-5" : ""}>{children}</div>
    </section>
  );
}

export function StatCard({ label, value, icon: Icon, tone = "brand", hint }) {
  const tones = {
    brand: "bg-brand-50 text-brand-700",
    sky: "bg-sky-50 text-sky-700",
    amber: "bg-amber-50 text-amber-700",
    rose: "bg-red-50 text-red-700",
    ink: "bg-ink-100 text-ink-700",
  };
  return (
    <div className="rounded-2xl border border-ink-100 bg-white p-5 shadow-sm">
      <div className="flex items-center justify-between">
        <p className="text-sm font-medium text-ink-500">{label}</p>
        {Icon && (
          <span className={`rounded-xl p-2 ${tones[tone]}`}>
            <Icon size={18} />
          </span>
        )}
      </div>
      <p className="mt-2 font-display text-3xl font-bold text-ink-900">{value ?? "—"}</p>
      {hint && <p className="mt-1 text-xs text-ink-400">{hint}</p>}
    </div>
  );
}

export function PageHeader({ title, subtitle, actions }) {
  return (
    <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
      <div>
        <h1 className="font-display text-2xl font-bold text-ink-900">{title}</h1>
        {subtitle && <p className="mt-1 text-sm text-ink-500">{subtitle}</p>}
      </div>
      {actions && <div className="flex flex-wrap gap-2">{actions}</div>}
    </div>
  );
}

// ---------------------------------------------------------------------------
export function Loading({ label = "Loading…" }) {
  return (
    <div className="flex items-center justify-center gap-2 py-12 text-sm text-ink-500" role="status">
      <Loader2 size={18} className="animate-spin text-brand-600" />
      {label}
    </div>
  );
}

export function EmptyState({ title = "Nothing here yet", message, icon: Icon = Inbox, action }) {
  return (
    <div className="flex flex-col items-center justify-center px-4 py-12 text-center">
      <span className="rounded-2xl bg-ink-100 p-3 text-ink-400">
        <Icon size={24} />
      </span>
      <p className="mt-3 font-semibold text-ink-800">{title}</p>
      {message && <p className="mt-1 max-w-md text-sm text-ink-500">{message}</p>}
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}

export function ErrorState({ error, onRetry }) {
  if (!error) return null;
  return (
    <div role="alert" className="flex flex-wrap items-start gap-3 rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">
      <AlertTriangle size={18} className="mt-0.5 shrink-0" />
      <div className="flex-1">
        <p className="font-semibold">{error.message || "Something went wrong."}</p>
        {error.reason && <p className="mt-0.5">{error.reason}</p>}
        {error.fields?.length > 0 && (
          <ul className="mt-1 list-disc pl-5">
            {error.fields.map((f) => (
              <li key={f.field}>
                {f.field}: {f.message}
              </li>
            ))}
          </ul>
        )}
      </div>
      {onRetry && (
        <button type="button" onClick={onRetry} className="font-semibold underline">
          Retry
        </button>
      )}
    </div>
  );
}

/** Rendered when the backend returns 403 ACCESS DENIED. Shows NO medical data. */
/** `children` (optional) is shown under the explanation, e.g. the doctor's "Request access" form. */
export function AccessDenied({ reason, access, patientName, children }) {
  return (
    <div role="alert" className="rounded-2xl border-2 border-red-200 bg-white p-6 shadow-sm">
      <div className="flex items-start gap-4">
        <span className="rounded-2xl bg-red-100 p-3 text-red-700">
          <ShieldX size={28} />
        </span>
        <div>
          <p className="font-display text-2xl font-extrabold tracking-wide text-red-700">ACCESS DENIED</p>
          {patientName && <p className="mt-1 text-sm text-ink-500">Patient: {patientName}</p>}
          <p className="mt-3 text-sm font-semibold text-ink-800">Reason:</p>
          <p className="text-sm text-ink-700">{reason || "You are not authorized to view this patient's records."}</p>
          {access && (
            <div className="mt-4 flex flex-wrap gap-2">
              <StatusBadge variant={access.consent ? "success" : "danger"}>Consent: {access.consent ? "YES" : "NO"}</StatusBadge>
              <StatusBadge variant="neutral" icon={false}>Previous visit: {access.previous_visit ? "YES" : "NO"}</StatusBadge>
              {!access.doctor_verified && <StatusBadge variant="warning">Doctor not verified</StatusBadge>}
            </div>
          )}
          <p className="mt-4 text-xs text-ink-400">
            Access requires the patient&apos;s permission (a previous visit is not needed). No medical information is shown.
          </p>
          {access && (!access.consent || !access.doctor_verified) && (
            <div className="mt-4 rounded-xl bg-ink-50 p-3 text-xs text-ink-600">
              <p className="font-semibold text-ink-700">How access can be granted</p>
              <ul className="mt-1 list-disc space-y-0.5 pl-4">
                {!access.doctor_verified && <li>An administrator verifies this doctor (Admin → Doctor Verification).</li>}
                {!access.consent && <li>The patient gives this doctor permission: ask them with <strong>Request access</strong>, or they can allow you on their Doctor access page.</li>}
              </ul>
            </div>
          )}
          {children}
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Fixed version lives in its own file (focus no longer jumps out of text boxes). Old code: frontend/backups/.
export { Modal } from "./Modal";

// ---------------------------------------------------------------------------
export function SearchInput({ value, onChange, placeholder = "Search…", ...props }) {
  return (
    <label className="relative block w-full sm:max-w-sm">
      <span className="sr-only">{placeholder}</span>
      <Search size={16} className="pointer-events-none absolute top-1/2 left-3 -translate-y-1/2 text-ink-400" />
      <input
        type="search"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        className="w-full rounded-xl border border-ink-200 bg-white py-2.5 pr-3 pl-9 text-sm outline-none focus:border-brand-400 focus:ring-2 focus:ring-brand-100"
        {...props}
      />
    </label>
  );
}

export function Field({ label, hint, children, required }) {
  return (
    <label className="block">
      <span className="mb-1.5 block text-sm font-semibold text-ink-700">
        {label}
        {required && <span className="text-red-600"> *</span>}
      </span>
      {children}
      {hint && <span className="mt-1 block text-xs text-ink-400">{hint}</span>}
    </label>
  );
}

export const inputCls =
  "w-full rounded-xl border border-ink-200 bg-white px-3 py-2.5 text-sm outline-none focus:border-brand-400 focus:ring-2 focus:ring-brand-100 disabled:bg-ink-50";

export function Select({ value, onChange, options, placeholder, ...props }) {
  return (
    <select value={value} onChange={(e) => onChange(e.target.value)} className={inputCls} {...props}>
      {placeholder !== undefined && <option value="">{placeholder}</option>}
      {options.map((o) => (
        <option key={o.value} value={o.value}>
          {o.label}
        </option>
      ))}
    </select>
  );
}

// ---------------------------------------------------------------------------
export function Table({ columns, rows, rowKey = "id", empty }) {
  if (!rows?.length) return empty || <EmptyState />;
  return (
    <div className="overflow-x-auto">
      <table className="min-w-full divide-y divide-ink-100 text-sm">
        <thead>
          <tr>
            {columns.map((c) => (
              <th key={c.key} scope="col" className="px-4 py-3 text-left text-xs font-semibold tracking-wide text-ink-500 uppercase">
                {c.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-ink-100">
          {rows.map((r) => (
            <tr key={r[rowKey]} className="hover:bg-ink-50/60">
              {columns.map((c) => (
                <td key={c.key} className="px-4 py-3 align-top text-ink-700">
                  {c.render ? c.render(r) : r[c.key]}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function Tabs({ tabs, active, onChange }) {
  return (
    <div className="flex flex-wrap gap-1 rounded-xl bg-ink-100 p-1" role="tablist">
      {tabs.map((t) => (
        <button
          key={t.value}
          type="button"
          role="tab"
          aria-selected={active === t.value}
          onClick={() => onChange(t.value)}
          className={`rounded-lg px-3 py-1.5 text-sm font-semibold transition-colors ${active === t.value ? "bg-white text-ink-900 shadow-sm" : "text-ink-500 hover:text-ink-800"}`}
        >
          {t.label}
        </button>
      ))}
    </div>
  );
}
