import { createContext, useContext, useMemo, useState } from "react";
import {
  admins,
  doctorsSeed,
  patientsSeed,
  doctorPatientAccessSeed,
  consultationsSeed,
  diagnosesSeed,
  prescriptionsSeed,
  documentsSeed,
  medicalRecordsSeed,
  accessHistorySeed,
  usersSeed,
} from "../data/mockData";
import { canAccessPatient, grantAccess, revokeAccess } from "../utils/accessControl";

const DataContext = createContext(null);

let recordCounter = 6000;
let documentCounter = 9000;
let accessLogCounter = 9500;

export function DataProvider({ children }) {
  const [doctors, setDoctors] = useState(doctorsSeed);
  const [patients] = useState(patientsSeed);
  const [users, setUsers] = useState(usersSeed);
  const [doctorPatientAccess, setDoctorPatientAccess] = useState(doctorPatientAccessSeed);
  const [consultations] = useState(consultationsSeed);
  const [diagnoses] = useState(diagnosesSeed);
  const [prescriptions] = useState(prescriptionsSeed);
  const [documents, setDocuments] = useState(documentsSeed);
  const [records, setRecords] = useState(medicalRecordsSeed);
  const [accessHistory, setAccessHistory] = useState(accessHistorySeed);

  const checkAccess = (doctorId, patientId) =>
    canAccessPatient(doctorPatientAccess, doctorId, patientId);

  const logAccessAttempt = (doctorId, patientId, result) => {
    const entry = {
      id: `AH-${++accessLogCounter}`,
      doctorId,
      patientId,
      timestamp: new Date().toISOString(),
      action: result.granted
        ? "Accessed patient record"
        : "Attempted to access patient record",
      result: result.granted ? "Access Granted" : "Access Denied",
      reason: result.granted ? null : result.reason,
    };
    setAccessHistory((prev) => [entry, ...prev]);
    return entry;
  };

  const attemptAccess = (doctorId, patientId) => {
    const result = checkAccess(doctorId, patientId);
    logAccessAttempt(doctorId, patientId, result);
    return result;
  };

  const grantDoctorAccess = (patientId, doctorId) => {
    setDoctorPatientAccess((prev) => grantAccess(prev, doctorId, patientId));
  };

  const revokeDoctorAccess = (patientId, doctorId) => {
    setDoctorPatientAccess((prev) => revokeAccess(prev, doctorId, patientId));
  };

  const addMedicalRecord = ({
    patientId,
    doctorId = null,
    type,
    date,
    hospital,
    documentName,
    description,
    uploadedBy,
    preview,
  }) => {
    const id = `REC-${++recordCounter}`;
    const docId = `DOC-${++documentCounter}`;

    const newRecord = {
      id,
      patientId,
      doctorId,
      type,
      date,
      hospital,
      documentName,
      status: "Active",
      description,
    };

    const newDocument = {
      id: docId,
      patientId,
      doctorId,
      date,
      type,
      name: documentName,
      hospital,
      status: "Active",
      uploadedBy,
      preview: preview || [
        `Patient ID: ${patientId}`,
        `Document: ${documentName}`,
        `Uploaded by: ${uploadedBy}`,
        `Date: ${date}`,
        "This is a simulated document preview for prototype purposes.",
      ],
    };

    setRecords((prev) => [newRecord, ...prev]);
    setDocuments((prev) => [newDocument, ...prev]);
    return newRecord;
  };

  // A patient may delete only a document they uploaded themselves. Documents and
  // records added by doctors are preserved (PNFR-11). Deleting an upload also
  // removes the medical record created with it.
  const deleteDocument = (documentId, requestedBy) => {
    const doc = documents.find((d) => d.id === documentId);
    if (!doc || doc.uploadedBy !== requestedBy) return false;

    setDocuments((prev) => prev.filter((d) => d.id !== documentId));
    setRecords((prev) =>
      prev.filter((r) => !(r.patientId === doc.patientId && r.documentName === doc.name))
    );
    return true;
  };

  const toggleUserStatus = (userId) => {
    setUsers((prev) =>
      prev.map((u) =>
        u.id === userId
          ? { ...u, status: u.status === "Active" ? "Inactive" : "Active" }
          : u
      )
    );
  };

  const setDoctorVerification = (doctorId, verified) => {
    setDoctors((prev) =>
      prev.map((d) => (d.id === doctorId ? { ...d, verified } : d))
    );
  };

  const value = useMemo(
    () => ({
      admins,
      doctors,
      patients,
      users,
      doctorPatientAccess,
      consultations,
      diagnoses,
      prescriptions,
      documents,
      records,
      accessHistory,
      checkAccess,
      attemptAccess,
      grantDoctorAccess,
      revokeDoctorAccess,
      addMedicalRecord,
      deleteDocument,
      toggleUserStatus,
      setDoctorVerification,
    }),
    [
      doctors,
      patients,
      users,
      doctorPatientAccess,
      consultations,
      diagnoses,
      prescriptions,
      documents,
      records,
      accessHistory,
    ]
  );

  return <DataContext.Provider value={value}>{children}</DataContext.Provider>;
}

export function useData() {
  const ctx = useContext(DataContext);
  if (!ctx) throw new Error("useData must be used within DataProvider");
  return ctx;
}
