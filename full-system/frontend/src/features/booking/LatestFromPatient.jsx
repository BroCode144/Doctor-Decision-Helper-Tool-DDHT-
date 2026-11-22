import { AlertTriangle, ClipboardList } from "lucide-react";
import { Link } from "react-router-dom";
import { api } from "../../lib/api";
import { formatDateTime } from "../../lib/format";
import { useApi } from "../../hooks/useApi";
import { Card, ErrorState, Loading } from "../../components/ui";
import { BookingAnswers, IntakeRecordView } from "./IntakeParts";

/** The doctor's "Latest from the patient": a short summary of what the patient said at their most recent booking. */
export default function LatestFromPatient({ patientId, decisionSupport }) {
  const { data, loading, error, reload } = useApi(() => api.get(`/patients/${patientId}/latest-from-patient`), [patientId]);
  if (loading) return <Loading />;
  if (error) return <ErrorState error={error} onRetry={reload} />;
  const l = data.latest;
  return (
    <Card title={<span className="flex items-center gap-2"><ClipboardList size={18} className="text-brand-600" /> Latest from the patient</span>}
      subtitle={l ? `Last updated ${formatDateTime(l.updated_at)} · booking for ${formatDateTime(l.appointment.start_at)}${l.appointment.doctor ? ` with ${l.appointment.doctor}` : ""}` : null}>
      {!l && <p className="text-sm text-ink-500">The patient hasn&apos;t answered the booking questions yet.</p>}
      {l && (
        <div className="space-y-3">
          {l.urgent.length > 0 && (
            <p role="alert" className="flex items-center gap-2 rounded-lg bg-red-50 px-3 py-2 text-sm font-semibold text-red-800">
              <AlertTriangle size={16} /> Warning signs: {l.urgent.join(", ")}
            </p>
          )}
          <ul className="list-disc space-y-1 pl-5 text-sm text-ink-800">
            {l.summary.filter((s) => !(l.urgent.length && s.startsWith("Warning signs"))).map((s) => <li key={s}>{s}</li>)}
          </ul>
          {decisionSupport && (
            <Link to="decision" className="inline-block text-sm font-semibold text-brand-700 hover:underline">See the risk results in Decision support →</Link>
          )}
          <details className="rounded-xl border border-ink-100 p-3">
            <summary className="cursor-pointer text-sm font-semibold text-ink-700">All of the patient&apos;s answers</summary>
            <div className="mt-3 space-y-3">
              <BookingAnswers answers={l.answers} />
              <IntakeRecordView record={l.intake_record} />
            </div>
          </details>
        </div>
      )}
    </Card>
  );
}
