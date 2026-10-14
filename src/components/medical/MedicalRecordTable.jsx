import { Eye } from "lucide-react";
import DataTable from "../ui/DataTable";
import StatusBadge from "../ui/StatusBadge";
import Button from "../ui/Button";
import { formatDate } from "../../utils/dataHelpers";

export default function MedicalRecordTable({ records, doctorNameFor, onView }) {
  const columns = [
    { key: "documentName", header: "Document" },
    { key: "type", header: "Type" },
    {
      key: "date",
      header: "Date",
      render: (row) => formatDate(row.date),
    },
    {
      key: "doctor",
      header: "Doctor",
      render: (row) => doctorNameFor?.(row.doctorId) || "—",
    },
    { key: "hospital", header: "Hospital" },
    {
      key: "status",
      header: "Status",
      render: (row) => (
        <StatusBadge variant={row.status === "Active" ? "success" : "neutral"}>
          {row.status}
        </StatusBadge>
      ),
    },
    {
      key: "actions",
      header: "",
      render: (row) =>
        onView ? (
          <Button variant="secondary" size="sm" icon={Eye} onClick={() => onView(row)}>
            View
          </Button>
        ) : null,
    },
  ];

  return (
    <DataTable
      columns={columns}
      data={records}
      emptyMessage="No medical records match the current filters."
    />
  );
}
