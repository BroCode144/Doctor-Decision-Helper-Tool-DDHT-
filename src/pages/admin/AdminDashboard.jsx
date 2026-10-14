import { useNavigate } from "react-router-dom";
import { Users, Stethoscope, BadgeCheck, ShieldCheck, ArrowRight, History } from "lucide-react";
import { useAuth } from "../../context/AuthContext";
import { useData } from "../../context/DataContext";
import DashboardCard from "../../components/ui/DashboardCard";
import StatusBadge from "../../components/ui/StatusBadge";
import { formatDateTime } from "../../utils/dataHelpers";

export default function AdminDashboard() {
  const { user } = useAuth();
  const { users, doctors, patients, accessHistory } = useData();
  const navigate = useNavigate();

  const verifiedDoctors = doctors.filter((d) => d.verified).length;
  const recentActivity = [...accessHistory]
    .sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp))
    .slice(0, 6);

  return (
    <div className="space-y-8">
      <div className="rounded-2xl border border-ink-100 bg-white p-6 shadow-sm">
        <h2 className="font-display text-xl font-bold text-ink-900">
          Welcome back, {user.name.split(" ")[0]}
        </h2>
        <p className="mt-1 text-sm text-ink-500">
          System-wide overview of users, doctors, and access activity.
        </p>
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <DashboardCard label="Total Users" value={users.length} icon={Users} tone="brand" />
        <DashboardCard label="Patients" value={patients.length} icon={Users} tone="sky" />
        <DashboardCard label="Doctors" value={doctors.length} icon={Stethoscope} tone="ink" />
        <DashboardCard
          label="Verified Doctors"
          value={`${verifiedDoctors} / ${doctors.length}`}
          icon={BadgeCheck}
          tone="amber"
        />
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <div className="rounded-2xl border border-ink-100 bg-white p-6 shadow-sm">
          <h3 className="font-display text-base font-bold text-ink-900">Quick Actions</h3>
          <div className="mt-4 space-y-2">
            <button
              type="button"
              onClick={() => navigate("/admin/users")}
              className="flex w-full items-center justify-between rounded-xl border border-ink-100 px-4 py-3 text-sm font-medium text-ink-700 hover:border-brand-200 hover:bg-brand-50/40"
            >
              <span className="flex items-center gap-2">
                <Users size={16} /> Manage users
              </span>
              <ArrowRight size={16} className="text-ink-300" />
            </button>
            <button
              type="button"
              onClick={() => navigate("/admin/doctors")}
              className="flex w-full items-center justify-between rounded-xl border border-ink-100 px-4 py-3 text-sm font-medium text-ink-700 hover:border-brand-200 hover:bg-brand-50/40"
            >
              <span className="flex items-center gap-2">
                <BadgeCheck size={16} /> Verify doctors
              </span>
              <ArrowRight size={16} className="text-ink-300" />
            </button>
            <button
              type="button"
              onClick={() => navigate("/admin/access-history")}
              className="flex w-full items-center justify-between rounded-xl border border-ink-100 px-4 py-3 text-sm font-medium text-ink-700 hover:border-brand-200 hover:bg-brand-50/40"
            >
              <span className="flex items-center gap-2">
                <History size={16} /> View access history
              </span>
              <ArrowRight size={16} className="text-ink-300" />
            </button>
          </div>
        </div>

        <div className="rounded-2xl border border-ink-100 bg-white p-6 shadow-sm">
          <div className="flex items-center justify-between">
            <h3 className="font-display text-base font-bold text-ink-900">Recent Access Activity</h3>
            <ShieldCheck size={18} className="text-ink-300" />
          </div>
          <div className="mt-4 space-y-2">
            {recentActivity.map((entry) => {
              const doctor = doctors.find((d) => d.id === entry.doctorId);
              const patient = patients.find((p) => p.id === entry.patientId);
              return (
                <div
                  key={entry.id}
                  className="flex items-center justify-between rounded-lg bg-ink-50/70 px-3 py-2 text-sm"
                >
                  <div>
                    <p className="font-medium text-ink-800">
                      {doctor?.name} → {patient?.name}
                    </p>
                    <p className="text-xs text-ink-400">{formatDateTime(entry.timestamp)}</p>
                  </div>
                  <StatusBadge variant={entry.result === "Access Granted" ? "success" : "danger"}>
                    {entry.result}
                  </StatusBadge>
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
}
