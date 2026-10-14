import { useAuth } from "../../context/AuthContext";
import { useData } from "../../context/DataContext";
import PatientProfileCard from "../../components/patient/PatientProfileCard";

export default function MyProfilePage() {
  const { user } = useAuth();
  const { patients } = useData();
  const patient = patients.find((p) => p.id === user.linkedId);

  return (
    <div className="space-y-6">
      <div>
        <h2 className="font-display text-lg font-bold text-ink-900">My Profile</h2>
        <p className="mt-1 text-sm text-ink-500">
          Your basic information as stored in the DDHT system.
        </p>
      </div>
      {patient && <PatientProfileCard patient={patient} />}
    </div>
  );
}
