import { useAuth } from "../../context/AuthContext";
import { useData } from "../../context/DataContext";
import MedicalTimeline from "../../components/medical/MedicalTimeline";
import { getPatientTimeline } from "../../utils/dataHelpers";

export default function MyTimelinePage() {
  const { user } = useAuth();
  const { consultations, diagnoses, prescriptions, records, doctors } = useData();

  const timelineEvents = getPatientTimeline(
    { consultations, diagnoses, prescriptions, records },
    user.linkedId,
    doctors
  );

  return (
    <div className="space-y-6">
      <div>
        <h2 className="font-display text-lg font-bold text-ink-900">Medical Timeline</h2>
        <p className="mt-1 text-sm text-ink-500">
          A chronological view of your consultations, diagnoses, prescriptions, and
          reports.
        </p>
      </div>
      <MedicalTimeline events={timelineEvents} />
    </div>
  );
}
