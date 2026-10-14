import { useMemo } from "react";
import { useAuth } from "../../context/AuthContext";
import { useData } from "../../context/DataContext";
import DataTable from "../../components/ui/DataTable";
import StatusBadge from "../../components/ui/StatusBadge";
import { formatDateTime } from "../../utils/dataHelpers";

export default function DoctorAccessHistoryPage() {
  const { user } = useAuth();
  const { accessHistory, patients } = useData();

  const doctorId = user.linkedId;

  const myHistory = useMemo(
    () =>
      accessHistory
        .filter((entry) => entry.doctorId === doctorId)
        .sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp)),
    [accessHistory, doctorId]
  );

  const columns = [
    {
      key: "patient",
      header: "Patient",
      render: (row) => patients.find((p) => p.id === row.patientId)?.name || row.patientId,
    },
    { key: "action", header: "Action" },
    {
      key: "timestamp",
      header: "Date & Time",
      render: (row) => formatDateTime(row.timestamp),
    },
    {
      key: "result",
      header: "Result",
      render: (row) => (
        <StatusBadge variant={row.result === "Access Granted" ? "success" : "danger"}>
          {row.result}
        </StatusBadge>
      ),
    },
    {
      key: "reason",
      header: "Reason",
      render: (row) => row.reason || "—",
    },
  ];

  return (
    <div className="space-y-6">
      <div>
        <h2 className="font-display text-lg font-bold text-ink-900">My Access History</h2>
        <p className="mt-1 text-sm text-ink-500">
          A complete log of your patient access attempts, granted or denied.
        </p>
      </div>
      <DataTable
        columns={columns}
        data={myHistory}
        emptyMessage="You have not attempted to access any patient records yet."
      />
    </div>
  );
}
