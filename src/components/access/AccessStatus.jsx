import { CheckCircle2, ShieldAlert } from "lucide-react";
import StatusBadge from "../ui/StatusBadge";

// Shown to a doctor right after a patient search — before any medical data renders.
export default function AccessStatus({ patientName, result }) {
  const { granted, previouslyVisited, authorized, reason } = result;

  return (
    <div
      className={`rounded-2xl border p-6 ${
        granted ? "border-brand-200 bg-brand-50" : "border-rose-200 bg-rose-50"
      }`}
    >
      <div className="flex items-start gap-4">
        <div
          className={`rounded-full p-2.5 ${
            granted ? "bg-brand-600 text-white" : "bg-rose-600 text-white"
          }`}
        >
          {granted ? <CheckCircle2 size={22} /> : <ShieldAlert size={22} />}
        </div>
        <div className="flex-1">
          <p className="font-display text-lg font-bold text-ink-900">
            {granted ? "Access Granted" : "Access Denied"}
          </p>
          <p className="mt-0.5 text-sm text-ink-600">
            Patient: <span className="font-semibold">{patientName}</span>
          </p>
          {!granted && reason && (
            <p className="mt-2 rounded-lg bg-white/70 px-3 py-2 text-sm font-medium text-rose-800">
              {reason}
            </p>
          )}

          <div className="mt-4 flex flex-wrap gap-2">
            <StatusBadge variant={previouslyVisited ? "success" : "danger"}>
              {previouslyVisited ? "Previously treated" : "Not previously treated"}
            </StatusBadge>
            <StatusBadge variant={authorized ? "success" : "danger"}>
              {authorized ? "Authorized by patient" : "Not authorized by patient"}
            </StatusBadge>
          </div>
        </div>
      </div>
    </div>
  );
}
