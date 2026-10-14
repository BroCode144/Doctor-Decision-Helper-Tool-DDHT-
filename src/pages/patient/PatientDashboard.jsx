import { useNavigate } from "react-router-dom";
import {
  FileText,
  ShieldCheck,
  Clock,
  UploadCloud,
  ArrowRight,
  ShieldQuestion,
} from "lucide-react";
import { useAuth } from "../../context/AuthContext";
import { useData } from "../../context/DataContext";
import DashboardCard from "../../components/ui/DashboardCard";
import MedicalRecordCard from "../../components/medical/MedicalRecordCard";
import EmptyState from "../../components/ui/EmptyState";
import { getPatientRecords } from "../../utils/dataHelpers";

export default function PatientDashboard() {
  const { user } = useAuth();
  const { patients, doctors, records, doctorPatientAccess } = useData();
  const navigate = useNavigate();

  const patientId = user.linkedId;
  const patient = patients.find((p) => p.id === patientId);
  const myRecords = getPatientRecords(records, patientId);
  const recentRecords = myRecords.slice(0, 3);

  const myConsents = doctorPatientAccess.filter((r) => r.patientId === patientId);
  const authorizedCount = myConsents.filter((r) => r.authorized).length;

  const doctorNameFor = (id) => doctors.find((d) => d.id === id)?.name || "Unknown Doctor";

  return (
    <div className="space-y-8">
      <div className="rounded-2xl border border-ink-100 bg-white p-6 shadow-sm">
        <h2 className="font-display text-xl font-bold text-ink-900">
          Welcome back, {patient?.name.split(" ")[0]}
        </h2>
        <p className="mt-1 text-sm text-ink-500">
          Here is a summary of your medical records and doctor access permissions.
        </p>
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <DashboardCard label="Total Medical Records" value={myRecords.length} icon={FileText} tone="brand" />
        <DashboardCard
          label="Doctors Authorized"
          value={authorizedCount}
          icon={ShieldCheck}
          tone="sky"
        />
        <DashboardCard
          label="Doctor Relationships"
          value={myConsents.length}
          icon={ShieldQuestion}
          tone="ink"
        />
        <DashboardCard label="Blood Group" value={patient?.bloodGroup || "—"} icon={Clock} tone="amber" />
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <div className="rounded-2xl border border-ink-100 bg-white p-6 shadow-sm">
          <div className="flex items-center justify-between">
            <h3 className="font-display text-base font-bold text-ink-900">Recent Records</h3>
            <button
              type="button"
              onClick={() => navigate("/patient/records")}
              className="text-sm font-medium text-brand-600 hover:text-brand-700"
            >
              View all
            </button>
          </div>
          <div className="mt-4 space-y-3">
            {recentRecords.length === 0 ? (
              <EmptyState icon={FileText} message="No medical records yet." />
            ) : (
              recentRecords.map((record) => (
                <MedicalRecordCard
                  key={record.id}
                  record={record}
                  doctorName={record.doctorId ? doctorNameFor(record.doctorId) : null}
                />
              ))
            )}
          </div>
        </div>

        <div className="rounded-2xl border border-ink-100 bg-white p-6 shadow-sm">
          <h3 className="font-display text-base font-bold text-ink-900">Quick Actions</h3>
          <div className="mt-4 space-y-2">
            <button
              type="button"
              onClick={() => navigate("/patient/upload")}
              className="flex w-full items-center justify-between rounded-xl border border-ink-100 px-4 py-3 text-sm font-medium text-ink-700 hover:border-brand-200 hover:bg-brand-50/40"
            >
              <span className="flex items-center gap-2">
                <UploadCloud size={16} /> Upload a medical record
              </span>
              <ArrowRight size={16} className="text-ink-300" />
            </button>
            <button
              type="button"
              onClick={() => navigate("/patient/consent")}
              className="flex w-full items-center justify-between rounded-xl border border-ink-100 px-4 py-3 text-sm font-medium text-ink-700 hover:border-brand-200 hover:bg-brand-50/40"
            >
              <span className="flex items-center gap-2">
                <ShieldQuestion size={16} /> Manage doctor consent
              </span>
              <ArrowRight size={16} className="text-ink-300" />
            </button>
            <button
              type="button"
              onClick={() => navigate("/patient/timeline")}
              className="flex w-full items-center justify-between rounded-xl border border-ink-100 px-4 py-3 text-sm font-medium text-ink-700 hover:border-brand-200 hover:bg-brand-50/40"
            >
              <span className="flex items-center gap-2">
                <Clock size={16} /> View medical timeline
              </span>
              <ArrowRight size={16} className="text-ink-300" />
            </button>
          </div>

          <h4 className="mt-6 text-sm font-semibold text-ink-700">Consent Status</h4>
          <div className="mt-2 space-y-2">
            {myConsents.length === 0 ? (
              <p className="text-sm text-ink-400">No doctor relationships yet.</p>
            ) : (
              myConsents.map((c) => (
                <div
                  key={c.doctorId}
                  className="flex items-center justify-between rounded-lg bg-ink-50/70 px-3 py-2 text-sm"
                >
                  <span className="font-medium text-ink-800">{doctorNameFor(c.doctorId)}</span>
                  <span
                    className={`text-xs font-semibold ${
                      c.authorized ? "text-brand-600" : "text-rose-600"
                    }`}
                  >
                    {c.authorized ? "Authorized" : "Not Authorized"}
                  </span>
                </div>
              ))
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
