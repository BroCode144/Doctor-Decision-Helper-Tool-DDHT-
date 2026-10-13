import { CheckCircle2, XCircle, Clock, AlertTriangle, Circle } from "lucide-react";

const VARIANTS = {
  success: {
    className: "bg-brand-50 text-brand-700 ring-1 ring-inset ring-brand-200",
    Icon: CheckCircle2,
  },
  danger: {
    className: "bg-rose-50 text-rose-700 ring-1 ring-inset ring-rose-200",
    Icon: XCircle,
  },
  warning: {
    className: "bg-amber-50 text-amber-700 ring-1 ring-inset ring-amber-200",
    Icon: AlertTriangle,
  },
  pending: {
    className: "bg-sky-50 text-sky-700 ring-1 ring-inset ring-sky-200",
    Icon: Clock,
  },
  neutral: {
    className: "bg-ink-100 text-ink-600 ring-1 ring-inset ring-ink-200",
    Icon: Circle,
  },
};

/**
 * Status indicator that never relies on color alone — always pairs an icon
 * with a text label for accessibility (PNFR: don't rely only on color).
 */
export default function StatusBadge({ variant = "neutral", children, icon = true }) {
  const { className, Icon } = VARIANTS[variant] || VARIANTS.neutral;
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-semibold ${className}`}
    >
      {icon && <Icon size={13} className="shrink-0" />}
      {children}
    </span>
  );
}
