import { useState } from "react";
import { FileText, ClipboardList, Pill, Stethoscope, Folder, Trash2 } from "lucide-react";
import { useAuth } from "../../context/AuthContext";
import { useData } from "../../context/DataContext";
import { useToast } from "../../context/ToastContext";
import MedicalRecordTable from "../../components/medical/MedicalRecordTable";
import DiagnosisList from "../../components/medical/DiagnosisList";
import PrescriptionList from "../../components/medical/PrescriptionList";
import ConsultationList from "../../components/medical/ConsultationList";
import DocumentCard from "../../components/medical/DocumentCard";
import DocumentViewer from "../../components/medical/DocumentViewer";
import FilterBar from "../../components/ui/FilterBar";
import EmptyState from "../../components/ui/EmptyState";
import Modal from "../../components/ui/Modal";
import Button from "../../components/ui/Button";
import { RECORD_TYPES } from "../../data/mockData";
import {
  getPatientRecords,
  getPatientDiagnoses,
  getPatientPrescriptions,
  getPatientConsultations,
  getPatientDocuments,
} from "../../utils/dataHelpers";

const TABS = [
  { key: "records", label: "Medical Records", icon: FileText },
  { key: "diagnoses", label: "Diagnoses", icon: ClipboardList },
  { key: "prescriptions", label: "Prescriptions", icon: Pill },
  { key: "consultations", label: "Consultations", icon: Stethoscope },
  { key: "documents", label: "Documents", icon: Folder },
];

export default function MyRecordsPage() {
  const { user } = useAuth();
  const { doctors, records, diagnoses, prescriptions, consultations, documents, deleteDocument } =
    useData();
  const { showToast } = useToast();
  const [activeTab, setActiveTab] = useState("records");
  const [typeFilter, setTypeFilter] = useState("All");
  const [dateFilter, setDateFilter] = useState("");
  const [viewingDocument, setViewingDocument] = useState(null);
  const [deletingDocument, setDeletingDocument] = useState(null);

  const confirmDelete = () => {
    const deleted = deleteDocument(deletingDocument.id, user.name);
    if (deleted) {
      showToast(`"${deletingDocument.name}" was deleted.`, "success");
    } else {
      showToast("You can only delete documents you uploaded yourself.", "error");
    }
    setDeletingDocument(null);
  };

  const patientId = user.linkedId;
  const doctorNameFor = (id) => (id ? doctors.find((d) => d.id === id)?.name : null) || "—";

  const myRecords = getPatientRecords(records, patientId).filter((r) => {
    const typeMatch = typeFilter === "All" || r.type === typeFilter;
    const dateMatch = !dateFilter || r.date === dateFilter;
    return typeMatch && dateMatch;
  });
  const myDiagnoses = getPatientDiagnoses(diagnoses, patientId);
  const myPrescriptions = getPatientPrescriptions(prescriptions, patientId);
  const myConsultations = getPatientConsultations(consultations, patientId);
  const myDocuments = getPatientDocuments(documents, patientId);

  return (
    <div className="space-y-6">
      <div>
        <h2 className="font-display text-lg font-bold text-ink-900">My Medical Records</h2>
        <p className="mt-1 text-sm text-ink-500">
          View your complete medical history. Records added by your doctors are preserved
          and cannot be deleted. You can delete documents you uploaded yourself.
        </p>
      </div>

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
          {activeTab === "records" && (
            <div className="space-y-4">
              <FilterBar
                filters={[
                  {
                    label: "Record Type",
                    value: typeFilter,
                    onChange: setTypeFilter,
                    options: [
                      { value: "All", label: "All Types" },
                      ...RECORD_TYPES.map((t) => ({ value: t, label: t })),
                    ],
                  },
                  {
                    label: "Date",
                    type: "date",
                    value: dateFilter,
                    onChange: setDateFilter,
                  },
                ]}
              />
              <MedicalRecordTable
                records={myRecords}
                doctorNameFor={doctorNameFor}
                onView={(record) => {
                  const doc = myDocuments.find((d) => d.name === record.documentName);
                  if (doc) setViewingDocument(doc);
                }}
              />
            </div>
          )}

          {activeTab === "diagnoses" && (
            <DiagnosisList diagnoses={myDiagnoses} doctorNameFor={doctorNameFor} />
          )}

          {activeTab === "prescriptions" && (
            <PrescriptionList prescriptions={myPrescriptions} doctorNameFor={doctorNameFor} />
          )}

          {activeTab === "consultations" && (
            <ConsultationList consultations={myConsultations} doctorNameFor={doctorNameFor} />
          )}

          {activeTab === "documents" && (
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {myDocuments.length === 0 ? (
                <EmptyState icon={Folder} message="No documents uploaded yet." />
              ) : (
                myDocuments.map((doc) => (
                  <DocumentCard
                    key={doc.id}
                    document={doc}
                    onView={setViewingDocument}
                    onDelete={doc.uploadedBy === user.name ? setDeletingDocument : undefined}
                  />
                ))
              )}
            </div>
          )}
        </div>
      </div>

      <DocumentViewer document={viewingDocument} onClose={() => setViewingDocument(null)} />

      <Modal
        open={!!deletingDocument}
        onClose={() => setDeletingDocument(null)}
        title="Delete this document?"
        size="sm"
        footer={
          <>
            <Button variant="secondary" size="sm" onClick={() => setDeletingDocument(null)}>
              Cancel
            </Button>
            <Button variant="danger" size="sm" icon={Trash2} onClick={confirmDelete}>
              Delete
            </Button>
          </>
        }
      >
        <p className="text-sm text-ink-600">
          <span className="font-semibold text-ink-900">{deletingDocument?.name}</span> and the
          medical record created with it will be removed from your records. This cannot be undone.
        </p>
      </Modal>
    </div>
  );
}
