import { useMemo, useState } from "react";
import { useData } from "../../context/DataContext";
import DataTable from "../../components/ui/DataTable";
import StatusBadge from "../../components/ui/StatusBadge";
import FilterBar from "../../components/ui/FilterBar";
import { formatDateTime } from "../../utils/dataHelpers";

export default function AccessHistoryPage() {
  const { accessHistory, doctors, patients } = useData();
  const [resultFilter, setResultFilter] = useState("All");
  const [doctorFilter, setDoctorFilter] = useState("All");

  const sorted = useMemo(
    () => [...accessHistory].sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp)),
    [accessHistory]
  );

  const filtered = sorted.filter((entry) => {
    const resultMatch = resultFilter === "All" || entry.result === resultFilter;
    const doctorMatch = doctorFilter === "All" || entry.doctorId === doctorFilter;
    return resultMatch && doctorMatch;
  });

  const columns = [
    {
      key: "doctor",
      header: "Doctor",
      render: (row) => doctors.find((d) => d.id === row.doctorId)?.name || row.doctorId,
    },
    {
      key: "patient",
      header: "Patient",
      render: (row) => patients.find((p) => p.id === row.patientId)?.name || row.patientId,
    },
    {
      key: "timestamp",
      header: "Date & Time",
      render: (row) => formatDateTime(row.timestamp),
    },
    { key: "action", header: "Action" },
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
        <h2 className="font-display text-lg font-bold text-ink-900">Access History</h2>
        <p className="mt-1 text-sm text-ink-500">
          Full audit trail of every doctor access attempt across the system.
        </p>
      </div>

      <div className="rounded-2xl border border-ink-100 bg-white p-5 shadow-sm">
        <FilterBar
          filters={[
            {
              label: "Result",
              value: resultFilter,
              onChange: setResultFilter,
              options: [
                { value: "All", label: "All Results" },
                { value: "Access Granted", label: "Access Granted" },
                { value: "Access Denied", label: "Access Denied" },
              ],
            },
            {
              label: "Doctor",
              value: doctorFilter,
              onChange: setDoctorFilter,
              options: [
                { value: "All", label: "All Doctors" },
                ...doctors.map((d) => ({ value: d.id, label: d.name })),
              ],
            },
          ]}
        />
      </div>

      <DataTable
        columns={columns}
        data={filtered}
        emptyMessage="No access history entries match your filters."
      />
    </div>
  );
}
