// ---------------------------------------------------------------------------
// Reusable data lookup / shaping helpers.
// These functions read from the arrays held in DataContext (passed in as
// arguments) so they stay pure and testable, and keep components thin.
// ---------------------------------------------------------------------------

export function getPatientById(patients, patientId) {
  return patients.find((p) => p.id === patientId) || null;
}

export function getDoctorById(doctors, doctorId) {
  return doctors.find((d) => d.id === doctorId) || null;
}

export function getPatientRecords(records, patientId) {
  return records
    .filter((r) => r.patientId === patientId)
    .sort((a, b) => new Date(b.date) - new Date(a.date));
}

export function getPatientConsultations(consultations, patientId) {
  return consultations
    .filter((c) => c.patientId === patientId)
    .sort((a, b) => new Date(b.date) - new Date(a.date));
}

export function getPatientDiagnoses(diagnoses, patientId) {
  return diagnoses
    .filter((d) => d.patientId === patientId)
    .sort((a, b) => new Date(b.date) - new Date(a.date));
}

export function getPatientPrescriptions(prescriptions, patientId) {
  return prescriptions
    .filter((p) => p.patientId === patientId)
    .sort((a, b) => new Date(b.date) - new Date(a.date));
}

export function getPatientDocuments(documents, patientId) {
  return documents
    .filter((doc) => doc.patientId === patientId)
    .sort((a, b) => new Date(b.date) - new Date(a.date));
}

/**
 * Builds a unified, chronologically-sorted timeline for a patient by
 * merging consultations, diagnoses, prescriptions, and lab/imaging records
 * into a single ordered list of events.
 */
export function getPatientTimeline(
  { consultations, diagnoses, prescriptions, records },
  patientId,
  doctors
) {
  const events = [];

  consultations
    .filter((c) => c.patientId === patientId)
    .forEach((c) => {
      const doctor = doctors.find((d) => d.id === c.doctorId);
      events.push({
        id: `timeline-${c.id}`,
        date: c.date,
        type: "Consultation",
        title: c.reason,
        doctor: doctor?.name || "Unknown Doctor",
        hospital: c.hospital,
        description: c.notes,
      });
    });

  diagnoses
    .filter((d) => d.patientId === patientId)
    .forEach((d) => {
      const doctor = doctors.find((doc) => doc.id === d.doctorId);
      events.push({
        id: `timeline-${d.id}`,
        date: d.date,
        type: "Diagnosis",
        title: d.diagnosis,
        doctor: doctor?.name || "Unknown Doctor",
        hospital: doctor?.hospital || "",
        description: d.notes,
      });
    });

  prescriptions
    .filter((p) => p.patientId === patientId)
    .forEach((p) => {
      const doctor = doctors.find((doc) => doc.id === p.doctorId);
      events.push({
        id: `timeline-${p.id}`,
        date: p.date,
        type: "Prescription",
        title: p.medication,
        doctor: doctor?.name || "Unknown Doctor",
        hospital: doctor?.hospital || "",
        description: p.instructions,
      });
    });

  records
    .filter(
      (r) =>
        r.patientId === patientId &&
        (r.type === "Lab Report" || r.type === "Imaging" || r.type === "Other")
    )
    .forEach((r) => {
      const doctor = doctors.find((doc) => doc.id === r.doctorId);
      events.push({
        id: `timeline-${r.id}`,
        date: r.date,
        type: r.type,
        title: r.documentName,
        doctor: doctor?.name || r.hospital,
        hospital: r.hospital,
        description: r.description,
      });
    });

  return events.sort((a, b) => new Date(b.date) - new Date(a.date));
}
