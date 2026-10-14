import { BadgeCheck, Clock } from "lucide-react";
import { useData } from "../../context/DataContext";
import { useToast } from "../../context/ToastContext";
import DataTable from "../../components/ui/DataTable";
import StatusBadge from "../../components/ui/StatusBadge";
import Button from "../../components/ui/Button";

export default function DoctorVerificationPage() {
  const { doctors, setDoctorVerification } = useData();
  const { showToast } = useToast();

  const handleToggle = (doctor) => {
    setDoctorVerification(doctor.id, !doctor.verified);
    showToast(
      `${doctor.name} marked as ${!doctor.verified ? "Verified" : "Pending"}.`,
      "success"
    );
  };

  const columns = [
    { key: "name", header: "Name" },
    { key: "id", header: "Doctor ID" },
    { key: "specialization", header: "Specialization" },
    { key: "hospital", header: "Hospital" },
    {
      key: "verified",
      header: "Verification Status",
      render: (row) => (
        <StatusBadge variant={row.verified ? "success" : "pending"}>
          {row.verified ? "Verified" : "Pending"}
        </StatusBadge>
      ),
    },
    {
      key: "actions",
      header: "Actions",
      render: (row) =>
        row.verified ? (
          <Button variant="secondary" size="sm" icon={Clock} onClick={() => handleToggle(row)}>
            Mark as Pending
          </Button>
        ) : (
          <Button variant="primary" size="sm" icon={BadgeCheck} onClick={() => handleToggle(row)}>
            Verify Doctor
          </Button>
        ),
    },
  ];

  return (
    <div className="space-y-6">
      <div>
        <h2 className="font-display text-lg font-bold text-ink-900">Doctor Verification</h2>
        <p className="mt-1 text-sm text-ink-500">
          Review registered doctors and verify their credentials before they can be
          fully trusted on the platform.
        </p>
      </div>
      <DataTable columns={columns} data={doctors} emptyMessage="No doctors registered yet." />
    </div>
  );
}
