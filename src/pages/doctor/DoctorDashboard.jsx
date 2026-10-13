import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Users, ShieldCheck, Stethoscope, History, Search, ArrowRight } from "lucide-react";
import { useAuth } from "../../context/AuthContext";
import { useData } from "../../context/DataContext";
import DashboardCard from "../../components/ui/DashboardCard";
import SearchBar from "../../components/ui/SearchBar";
import PatientCard from "../../components/patient/PatientCard";
import EmptyState from "../../components/ui/EmptyState";
import StatusBadge from "../../components/ui/StatusBadge";
import { formatDateTime } from "../../utils/dataHelpers";

export default function DoctorDashboard() {
  const { user } = useAuth();
  const { patients, doctorPatientAccess, accessHistory, consultations } = useData();
  const navigate = useNavigate();
  const [query, setQuery] = useState("");

  const doctorId = user.linkedId;

  const myRelationships = doctorPatientAccess.filter((r) => r.doctorId === doctorId);
  const totalPatients = myRelationships.filter((r) => r.previouslyVisited).length;
  const authorizedPatients = myRelationships.filter(
    (r) => r.previouslyVisited && r.authorized
  ).length;
  const myConsultations = consultations.filter((c) => c.doctorId === doctorId).length;
  const pendingItems = myRelationships.filter(
    (r) => r.previouslyVisited && !r.authorized
  ).length;

  const myAccessHistory = useMemo(
    () =>
      accessHistory
        .filter((entry) => entry.doctorId === doctorId)
        .sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp))
        .slice(0, 5),
    [accessHistory, doctorId]
  );

  // Only patients whose records this doctor actually opened (access granted);
  // a denied attempt is not an access, so it never lists the patient here.
  const recentPatientIds = [
    ...new Set(
      accessHistory
        .filter((entry) => entry.doctorId === doctorId && entry.result === "Access Granted")
        .sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp))
        .map((entry) => entry.patientId)
    ),
  ].slice(0, 4);
  const recentPatients = recentPatientIds
    .map((id) => patients.find((p) => p.id === id))
    .filter(Boolean);

  const filteredPatients = query
    ? patients.filter(
        (p) =>
          p.name.toLowerCase().includes(query.toLowerCase()) ||
          p.id.toLowerCase().includes(query.toLowerCase())
      )
    : [];

  const goToPatient = (patientId) => navigate(`/doctor/search?patient=${patientId}`);

  return (
    <div className="space-y-8">
      <div className="rounded-2xl border border-ink-100 bg-white p-6 shadow-sm">
        <h2 className="font-display text-xl font-bold text-ink-900">
          Welcome back, {user.name.split(" ")[0] === "Dr." ? user.name : user.name}
        </h2>
        <p className="mt-1 text-sm text-ink-500">
          Here's an overview of your patient access and recent activity.
        </p>
        <div className="mt-4">
          <SearchBar
            value={query}
            onChange={setQuery}
            placeholder="Quick search: patient name or ID..."
            label="Quick patient search"
          />
          {query && (
            <div className="mt-3 space-y-2">
              {filteredPatients.length === 0 ? (
                <p className="px-1 text-sm text-ink-400">No patients matched "{query}".</p>
              ) : (
                filteredPatients
                  .slice(0, 4)
                  .map((p) => (
                    <PatientCard key={p.id} patient={p} onClick={() => goToPatient(p.id)} />
                  ))
              )}
            </div>
          )}
        </div>
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <DashboardCard label="Total Patients Treated" value={totalPatients} icon={Users} tone="brand" />
        <DashboardCard
          label="Authorized Patients"
          value={authorizedPatients}
          icon={ShieldCheck}
          tone="sky"
        />
        <DashboardCard
          label="Recent Consultations"
          value={myConsultations}
          icon={Stethoscope}
          tone="ink"
        />
        <DashboardCard
          label="Pending (Awaiting Authorization)"
          value={pendingItems}
          icon={History}
          tone="amber"
        />
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <div className="rounded-2xl border border-ink-100 bg-white p-6 shadow-sm">
          <div className="flex items-center justify-between">
            <h3 className="font-display text-base font-bold text-ink-900">
              Recently Accessed Patients
            </h3>
          </div>
          <div className="mt-4 space-y-2">
            {recentPatients.length === 0 ? (
              <EmptyState message="No patients accessed yet." />
            ) : (
              recentPatients.map((p) => (
                <PatientCard key={p.id} patient={p} onClick={() => goToPatient(p.id)} />
              ))
            )}
          </div>
        </div>

        <div className="rounded-2xl border border-ink-100 bg-white p-6 shadow-sm">
          <h3 className="font-display text-base font-bold text-ink-900">Quick Actions</h3>
          <div className="mt-4 space-y-2">
            <button
              type="button"
              onClick={() => navigate("/doctor/search")}
              className="flex w-full items-center justify-between rounded-xl border border-ink-100 px-4 py-3 text-sm font-medium text-ink-700 hover:border-brand-200 hover:bg-brand-50/40"
            >
              <span className="flex items-center gap-2">
                <Search size={16} /> Search for a patient
              </span>
              <ArrowRight size={16} className="text-ink-300" />
            </button>
            <button
              type="button"
              onClick={() => navigate("/doctor/access-history")}
              className="flex w-full items-center justify-between rounded-xl border border-ink-100 px-4 py-3 text-sm font-medium text-ink-700 hover:border-brand-200 hover:bg-brand-50/40"
            >
              <span className="flex items-center gap-2">
                <History size={16} /> View my access history
              </span>
              <ArrowRight size={16} className="text-ink-300" />
            </button>
          </div>

          <h4 className="mt-6 text-sm font-semibold text-ink-700">Recent Access Attempts</h4>
          <div className="mt-2 space-y-2">
            {myAccessHistory.length === 0 ? (
              <p className="text-sm text-ink-400">No access attempts logged yet.</p>
            ) : (
              myAccessHistory.map((entry) => {
                const patient = patients.find((p) => p.id === entry.patientId);
                return (
                  <div
                    key={entry.id}
                    className="flex items-center justify-between rounded-lg bg-ink-50/70 px-3 py-2 text-sm"
                  >
                    <div>
                      <p className="font-medium text-ink-800">{patient?.name || entry.patientId}</p>
                      <p className="text-xs text-ink-400">{formatDateTime(entry.timestamp)}</p>
                    </div>
                    <StatusBadge variant={entry.result === "Access Granted" ? "success" : "danger"}>
                      {entry.result}
                    </StatusBadge>
                  </div>
                );
              })
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
