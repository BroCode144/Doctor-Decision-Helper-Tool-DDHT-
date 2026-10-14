import { ShieldCheck, ShieldOff, CheckCircle2, XCircle } from "lucide-react";
import StatusBadge from "../ui/StatusBadge";
import Button from "../ui/Button";

export default function ConsentCard({ doctor, previouslyVisited, authorized, onGrant, onRevoke }) {
  return (
    <div className="flex flex-col gap-4 rounded-2xl border border-ink-100 bg-white p-5 shadow-sm sm:flex-row sm:items-center sm:justify-between">
      <div className="flex items-center gap-3">
        <div className="flex h-11 w-11 items-center justify-center rounded-full bg-brand-100 text-sm font-bold text-brand-700">
          {doctor.initials}
        </div>
        <div>
          <p className="font-semibold text-ink-900">{doctor.name}</p>
          <p className="text-sm text-ink-500">
            {doctor.specialization} · {doctor.hospital}
          </p>
          <div className="mt-1.5 flex flex-wrap gap-2">
            <StatusBadge variant={previouslyVisited ? "success" : "neutral"} icon={false}>
              {previouslyVisited ? <CheckCircle2 size={13} /> : <XCircle size={13} />}
              Previous Visit: {previouslyVisited ? "Yes" : "No"}
            </StatusBadge>
            <StatusBadge variant={authorized ? "success" : "danger"} icon={false}>
              {authorized ? <ShieldCheck size={13} /> : <ShieldOff size={13} />}
              Access: {authorized ? "Authorized" : "Not Authorized"}
            </StatusBadge>
          </div>
        </div>
      </div>

      <div className="shrink-0">
        {authorized ? (
          <Button variant="danger" size="sm" icon={ShieldOff} onClick={onRevoke}>
            Revoke Access
          </Button>
        ) : (
          <Button variant="primary" size="sm" icon={ShieldCheck} onClick={onGrant}>
            Grant Access
          </Button>
        )}
      </div>
    </div>
  );
}
