import { useAuth } from "../../context/AuthContext";
import { useData } from "../../context/DataContext";
import { useToast } from "../../context/ToastContext";
import ConsentCard from "../../components/consent/ConsentCard";
import EmptyState from "../../components/ui/EmptyState";
import { ShieldQuestion } from "lucide-react";

export default function ConsentManagementPage() {
  const { user } = useAuth();
  const { doctors, doctorPatientAccess, grantDoctorAccess, revokeDoctorAccess } = useData();
  const { showToast } = useToast();

  const patientId = user.linkedId;
  const myRelationships = doctorPatientAccess.filter((r) => r.patientId === patientId);

  const rows = myRelationships
    .map((rel) => ({
      ...rel,
      doctor: doctors.find((d) => d.id === rel.doctorId),
    }))
    .filter((row) => row.doctor);

  const handleGrant = (doctorId, doctorName) => {
    grantDoctorAccess(patientId, doctorId);
    showToast(`Access granted to ${doctorName}.`, "success");
  };

  const handleRevoke = (doctorId, doctorName) => {
    revokeDoctorAccess(patientId, doctorId);
    showToast(`Access revoked for ${doctorName}.`, "info");
  };

  return (
    <div className="space-y-6">
      <div>
        <h2 className="font-display text-lg font-bold text-ink-900">Consent Management</h2>
        <p className="mt-1 text-sm text-ink-500">
          Control which doctors can access your medical records. Revoking access takes
          effect immediately.
        </p>
      </div>

      {rows.length === 0 ? (
        <EmptyState icon={ShieldQuestion} message="No doctors found for your account." />
      ) : (
        <div className="space-y-3">
          {rows.map((row) => (
            <ConsentCard
              key={row.doctorId}
              doctor={row.doctor}
              previouslyVisited={row.previouslyVisited}
              authorized={row.authorized}
              onGrant={() => handleGrant(row.doctorId, row.doctor.name)}
              onRevoke={() => handleRevoke(row.doctorId, row.doctor.name)}
            />
          ))}
        </div>
      )}
    </div>
  );
}
