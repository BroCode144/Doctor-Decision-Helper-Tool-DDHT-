import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import {
  Search as SearchIcon,
  User,
  Clock,
  FileText,
  ClipboardList,
  Pill,
  Stethoscope,
  Folder,
} from "lucide-react";
import { useAuth } from "../../context/AuthContext";
import { useData } from "../../context/DataContext";
import { useToast } from "../../context/ToastContext";
import SearchBar from "../../components/ui/SearchBar";
import PatientCard from "../../components/patient/PatientCard";
import PatientProfileCard from "../../components/patient/PatientProfileCard";
import AccessStatus from "../../components/access/AccessStatus";
import EmptyState from "../../components/ui/EmptyState";
import MedicalTimeline from "../../components/medical/MedicalTimeline";
import MedicalRecordTable from "../../components/medical/MedicalRecordTable";
import DiagnosisList from "../../components/medical/DiagnosisList";
import PrescriptionList from "../../components/medical/PrescriptionList";
import ConsultationList from "../../components/medical/ConsultationList";
import DocumentCard from "../../components/medical/DocumentCard";
import DocumentViewer from "../../components/medical/DocumentViewer";
import FilterBar from "../../components/ui/FilterBar";
import { RECORD_TYPES } from "../../data/mockData";
import {
  getPatientRecords,
  getPatientConsultations,
  getPatientDiagnoses,
  getPatientPrescriptions,
  getPatientDocuments,
  getPatientTimeline,
} from "../../utils/dataHelpers";

const TABS = [
  { key: "profile", label: "Profile", icon: User },
  { key: "timeline", label: "Timeline", icon: Clock },
  { key: "records", label: "Medical Records", icon: FileText },
  { key: "diagnoses", label: "Diagnoses", icon: ClipboardList },
  { key: "prescriptions", label: "Prescriptions", icon: Pill },
  { key: "consultations", label: "Consultations", icon: Stethoscope },
  { key: "documents", label: "Documents", icon: Folder },
];

export default function PatientSearchPage() {
  const { user } = useAuth();
  const {
    patients,
    doctors,
    doctorPatientAccess,
    consultations,
    diagnoses,
    prescriptions,
    documents,
    records,
    attemptAccess,
  } = useData();
  const { showToast } = useToast();
  const [searchParams, setSearchParams] = useSearchParams();

  const doctorId = user.linkedId;

  const [query, setQuery] = useState("");
  const [selectedPatient, setSelectedPatient] = useState(null);
  const [accessResult, setAccessResult] = useState(null);
  const [activeTab, setActiveTab] = useState("profile");
  const [viewingDocument, setViewingDocument] = useState(null);
  const [recordTypeFilter, setRecordTypeFilter] = useState("All");
  const [recordDateFilter, setRecordDateFilter] = useState("");

  const doctorNameFor = (id) => doctors.find((d) => d.id === id)?.name || "Unknown Doctor";

  const openPatient = (patient) => {
    const result = attemptAccess(doctorId, patient.id);
    setSelectedPatient(patient);
    setAccessResult(result);
    setActiveTab("profile");
    setRecordTypeFilter("All");
    setRecordDateFilter("");

    if (result.granted) {
      showToast(`Access granted to ${patient.name}'s records.`, "success");
    } else {
      showToast(`Access denied for ${patient.name}.`, "error");
    }
  };

  useEffect(() => {
    const patientId = searchParams.get("patient");
    if (patientId) {
      const patient = patients.find((p) => p.id === patientId);
      if (patient) openPatient(patient);
      setSearchParams({}, { replace: true });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const filteredPatients = useMemo(() => {
    if (!query.trim()) return [];
    const q = query.trim().toLowerCase();
    return patients.filter(
      (p) => p.name.toLowerCase().includes(q) || p.id.toLowerCase().includes(q)
    );
  }, [query, patients]);

  // Patients this doctor has treated or consulted. Listing them only shows
  // names; opening one still runs the full access check like a search does.
  const myPatients = useMemo(() => {
    const ids = new Set([
      ...doctorPatientAccess
        .filter((a) => a.doctorId === doctorId && a.previouslyVisited)
        .map((a) => a.patientId),
      ...consultations.filter((c) => c.doctorId === doctorId).map((c) => c.patientId),
    ]);
    return patients.filter((p) => ids.has(p.id));
  }, [doctorPatientAccess, consultations, patients, doctorId]);

  const patientRecords = selectedPatient
    ? getPatientRecords(records, selectedPatient.id)
    : [];
  const visibleRecords = patientRecords.filter((r) => {
    const typeMatch = recordTypeFilter === "All" || r.type === recordTypeFilter;
    const dateMatch = !recordDateFilter || r.date === recordDateFilter;
    return typeMatch && dateMatch;
  });

  const timelineEvents = selectedPatient
    ? getPatientTimeline(
        { consultations, diagnoses, prescriptions, records },
        selectedPatient.id,
        doctors
      )
    : [];

  const patientDiagnoses = selectedPatient
    ? getPatientDiagnoses(diagnoses, selectedPatient.id)
    : [];
  const patientPrescriptions = selectedPatient
    ? getPatientPrescriptions(prescriptions, selectedPatient.id)
    : [];
  const patientConsultations = selectedPatient
    ? getPatientConsultations(consultations, selectedPatient.id)
    : [];
  const patientDocuments = selectedPatient
    ? getPatientDocuments(documents, selectedPatient.id)
    : [];

  return (
    <div className="space-y-6">
      <div className="rounded-2xl border border-ink-100 bg-white p-6 shadow-sm">
        <h2 className="font-display text-lg font-bold text-ink-900">Patient Search</h2>
        <p className="mt-1 text-sm text-ink-500">
          Search for a patient by name or ID. Selecting a patient checks your access
          eligibility before any medical data is shown.
        </p>
        <div className="mt-4">
          <SearchBar
            value={query}
            onChange={setQuery}
            placeholder="Search by patient name or ID (e.g. Rahul Sharma, P001)"
            label="Search patients"
          />
        </div>

        {query.trim() ? (
          <div className="mt-4 space-y-2">
            {filteredPatients.length === 0 ? (
              <EmptyState icon={SearchIcon} message={`No patients found for "${query}".`} />
            ) : (
              filteredPatients.map((p) => (
                <PatientCard key={p.id} patient={p} onClick={() => openPatient(p)} />
              ))
            )}
          </div>
        ) : (
          <div className="mt-5">
            <h3 className="text-sm font-semibold text-ink-900">
              My patients ({myPatients.length})
            </h3>
            <p className="mt-0.5 text-xs text-ink-500">
              Patients you have treated or consulted. Opening a patient still checks
              that they have authorized you.
            </p>
            <div className="mt-3 space-y-2">
              {myPatients.length === 0 ? (
                <EmptyState icon={User} message="You have not treated or consulted any patients yet." />
              ) : (
                myPatients.map((p) => (
                  <PatientCard key={p.id} patient={p} onClick={() => openPatient(p)} />
                ))
              )}
            </div>
          </div>
        )}
      </div>

      {selectedPatient && accessResult && (
        <AccessStatus patientName={selectedPatient.name} result={accessResult} />
      )}

      {selectedPatient && accessResult?.granted && (
        <div className="rounded-2xl border border-ink-100 bg-white shadow-sm">
          <div className="flex gap-1 overflow-x-auto border-b border-ink-100 px-3 pt-3">
            {TABS.map(({ key, label, icon: Icon }) => (
              <button
                key={key}
                type="button"
                onClick={() => setActiveTab(key)}
                className={`flex shrink-0 items-center gap-1.5 rounded-t-xl border-b-2 px-4 py-2.5 text-sm font-medium transition-colors ${
                  activeTab === key
                    ? "border-brand-600 text-brand-700"
                    : "border-transparent text-ink-500 hover:text-ink-800"
                }`}
              >
                <Icon size={15} />
                {label}
              </button>
            ))}
          </div>

          <div className="p-6">
            {activeTab === "profile" && <PatientProfileCard patient={selectedPatient} />}

            {activeTab === "timeline" && <MedicalTimeline events={timelineEvents} />}

            {activeTab === "records" && (
              <div className="space-y-4">
                <FilterBar
                  filters={[
                    {
                      label: "Record Type",
                      value: recordTypeFilter,
                      onChange: setRecordTypeFilter,
                      options: [
                        { value: "All", label: "All Types" },
                        ...RECORD_TYPES.map((t) => ({ value: t, label: t })),
                      ],
                    },
                    {
                      label: "Date",
                      type: "date",
                      value: recordDateFilter,
                      onChange: setRecordDateFilter,
                    },
                  ]}
                />
                <MedicalRecordTable
                  records={visibleRecords}
                  doctorNameFor={doctorNameFor}
                  onView={(record) => {
                    const doc = patientDocuments.find(
                      (d) => d.name === record.documentName
                    );
                    if (doc) setViewingDocument(doc);
                  }}
                />
              </div>
            )}

            {activeTab === "diagnoses" && (
              <DiagnosisList diagnoses={patientDiagnoses} doctorNameFor={doctorNameFor} />
            )}

            {activeTab === "prescriptions" && (
              <PrescriptionList
                prescriptions={patientPrescriptions}
                doctorNameFor={doctorNameFor}
              />
            )}

            {activeTab === "consultations" && (
              <ConsultationList
                consultations={patientConsultations}
                doctorNameFor={doctorNameFor}
              />
            )}

            {activeTab === "documents" && (
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
                {patientDocuments.length === 0 ? (
                  <EmptyState icon={Folder} message="No documents uploaded for this patient." />
                ) : (
                  patientDocuments.map((doc) => (
                    <DocumentCard key={doc.id} document={doc} onView={setViewingDocument} />
                  ))
                )}
              </div>
            )}
          </div>
        </div>
      )}

      <DocumentViewer document={viewingDocument} onClose={() => setViewingDocument(null)} />
    </div>
  );
}
