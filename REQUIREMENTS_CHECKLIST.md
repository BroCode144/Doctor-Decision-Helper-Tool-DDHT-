# DDHT — Requirements Checklist

Status of every functional (PFR) and non-functional (PNFR) requirement,
verified against the running application (not assumed).

## Prototype Functional Requirements (PFR)

| Requirement | Implementation | Status |
|---|---|---|
| PFR-01 — User Login | `src/pages/LoginPage.jsx` + `AuthContext.login()`; mock credential check against `usersSeed`, role-based redirect, one-click demo account fill for all three roles | Complete |
| PFR-02 — Role-Based Access | `App.jsx` route tree scoped per role via `ProtectedRoute`; `components/layout/navConfig.js` renders only the nav items for the logged-in role | Complete |
| PFR-03 — Logout | `Header.jsx` "Log out" button calls `AuthContext.logout()` and redirects to `/login` | Complete |
| PFR-04 — Doctor Dashboard | `pages/doctor/DoctorDashboard.jsx` — welcome section, quick patient search, stat cards, recently accessed patients, quick actions, recent access attempts | Complete |
| PFR-05 — Authorized Patient Search | `pages/doctor/PatientSearchPage.jsx` — before searching, lists "My patients": every patient the doctor has treated (`previouslyVisited`) or consulted (names only, no medical data); search never auto-grants access; opening a patient from the list or the search runs `attemptAccess()` and renders `AccessStatus` before any tabs/data appear | Complete |
| PFR-06 — Patient Profile | `components/patient/PatientProfileCard.jsx` — name, ID, DOB, gender, phone, email, blood group, address, emergency contact (mock data) | Complete |
| PFR-07 — Medical History | Diagnoses/Prescriptions/Consultations tabs on `PatientSearchPage`, only rendered after `accessResult.granted === true` | Complete |
| PFR-08 — Chronological Medical Timeline | `utils/dataHelpers.getPatientTimeline()` merges consultations, diagnoses, prescriptions, and lab/imaging records, sorted by date; rendered via `components/medical/MedicalTimeline.jsx` | Complete |
| PFR-09 — Medical Document Viewing | `components/medical/DocumentViewer.jsx` modal with simulated document preview text and metadata | Complete |
| PFR-10 — Medical Record Filtering | `components/ui/FilterBar.jsx` on both `PatientSearchPage` (doctor) and `MyRecordsPage` (patient) — filter by record type and date | Complete |
| PFR-11 — Medical Record Upload | `pages/patient/UploadRecordPage.jsx` — simulated file picker + form, calls `DataContext.addMedicalRecord()`, appears immediately in records list | Complete |
| PFR-12 — Medical Record Information | `components/medical/MedicalRecordCard.jsx` / `MedicalRecordTable.jsx` — type, date, doctor, hospital, document name, status | Complete |
| PFR-13 — Diagnosis Viewing | `components/medical/DiagnosisList.jsx` — diagnosis, date, doctor, notes/status; static mock data only, no AI-generated content | Complete |
| PFR-14 — Prescription Viewing | `components/medical/PrescriptionList.jsx` — medication, date, doctor, dosage/instructions, status; view-only, no recommendations | Complete |
| PFR-15 — Consultation Record Viewing | `components/medical/ConsultationList.jsx` — date, doctor, hospital, reason, notes, follow-up status | Complete |
| PFR-16 — Patient Dashboard | `pages/patient/PatientDashboard.jsx` — welcome, stat cards, recent records, consent status, quick actions | Complete |
| PFR-17 — Patient Record Viewing | `pages/patient/MyRecordsPage.jsx` (records/diagnoses/prescriptions/consultations/documents tabs) + `MyTimelinePage.jsx`; no doctor authorization required for a patient to view their own data | Complete |
| PFR-18 — Patient Record Upload | Same as PFR-11 — `UploadRecordPage.jsx`; metadata stored in `DataContext` local state, no server required | Complete |
| PFR-19 — Consent Management | `pages/patient/ConsentManagementPage.jsx` + `components/consent/ConsentCard.jsx` — grant/revoke per doctor; `DataContext.grantDoctorAccess` / `revokeDoctorAccess` update state immediately, verified to propagate to the doctor's next access attempt in the same session | Complete |
| PFR-20 — Admin Dashboard | `pages/admin/AdminDashboard.jsx` — total users, patients, doctors, verified doctors, recent access activity | Complete |
| PFR-21 — User Management | `pages/admin/UserManagementPage.jsx` — table with name/ID/role/email/status/registration date, search + role filter, View detail modal, Activate/Deactivate action | Complete |
| PFR-22 — Doctor Verification | `pages/admin/DoctorVerificationPage.jsx` — name, ID, specialization, hospital, verification status, Verify / Mark as Pending actions | Complete |
| PFR-23 — Access History | `pages/admin/AccessHistoryPage.jsx` (system-wide, filterable by result/doctor) and `pages/doctor/DoctorAccessHistoryPage.jsx` (doctor's own log); every attempt is logged via `DataContext.logAccessAttempt()` with user, patient, timestamp, action, result, and reason | Complete |

## Prototype Non-Functional Requirements (PNFR)

| Requirement | Implementation | Status |
|---|---|---|
| PNFR-01 — Authentication Security | Mock authentication only (`AuthContext.login`); explicitly documented as non-production in the README and on the login page | Complete (as a prototype) |
| PNFR-02 — Authorization | Centralized in `utils/accessControl.js`; `canAccessPatient()` requires `previouslyVisited === true AND authorized === true`; no UI component hardcodes an access decision | Complete |
| PNFR-03 — Patient Data Privacy | `PatientSearchPage.jsx` only renders the tabbed medical data block when `accessResult.granted` is true; denied doctors see only the `AccessStatus` denial panel | Complete |
| PNFR-04 — Data Isolation | All lookups are filtered by `patientId` (`getPatientRecords`, `getPatientDiagnoses`, etc. in `utils/dataHelpers.js`); no shared/global record list is ever rendered unfiltered | Complete |
| PNFR-05 — Simple Interface | Single design system (`src/index.css` tokens), consistent card/table/tab patterns reused across all three roles | Complete |
| PNFR-06 — Consistent Navigation | `components/layout/Sidebar.jsx`, `Header.jsx`, `DashboardLayout.jsx` shared by every authenticated route via nested routing in `App.jsx` | Complete |
| PNFR-07 — Readability | Consistent typography scale (Inter/Manrope), spacing, status badges, and card/table layouts throughout | Complete |
| PNFR-08 — Response Time | Purely client-side state (React Context + `useState`), no network calls; all interactions are instant | Complete |
| PNFR-09 — Data Integrity | Relationships modeled explicitly: `doctorPatientAccess[]` (doctor↔patient), records/diagnoses/prescriptions/consultations/documents all keyed by `patientId`; verified no cross-patient leakage during testing | Complete |
| PNFR-10 — Error Handling | `components/ui/ErrorMessage.jsx` for login failures; `EmptyState.jsx` for "no results" everywhere (search, records, documents, access history); no raw stack traces or technical errors surfaced to the user | Complete |
| PNFR-11 — Record Preservation | Records and documents added by doctors cannot be deleted by anyone; record rows only expose "View". A patient may delete only a document they uploaded themselves (`DataContext.deleteDocument()` checks `uploadedBy` against the requester; Delete button and confirmation dialog on `MyRecordsPage` Documents tab). Doctors and admins have no delete action | Complete |
| PNFR-12 — Record Accuracy | Mock data is static and only changes through explicit, deliberate user actions (upload, consent grant/revoke, verification, activation) — never silently altered | Complete |

## Verified test flows (manually exercised in-browser)

- [x] Patient login works (`patient@ddht.demo`)
- [x] Doctor login works (`doctor@ddht.demo`)
- [x] Admin login works (`admin@ddht.demo`)
- [x] Logout returns to `/login`
- [x] Doctor can search patients by name/ID
- [x] Patient Search lists the doctor's treated/consulted patients before searching (Dr. Raj Mehta: Rahul Sharma, Priya Shah, Neha Kapoor); opening Priya Shah from the list is still denied
- [x] Doctor **granted** access to Rahul Sharma (previously treated + authorized)
- [x] Doctor **denied** access to Priya Shah (treated, not authorized) — correct reason shown
- [x] Doctor **denied** access to Aman Patel (authorized, never treated) — correct reason shown
- [x] No medical data rendered on any denied attempt
- [x] Patient can revoke a doctor's access from Consent Management
- [x] Revoking access immediately causes that doctor's next access attempt to be denied
- [x] Patient can view their own records/timeline/documents without authorization checks
- [x] Patient can upload a new record; it appears instantly in the records table
- [x] Admin can view and search/filter users, and activate/deactivate an account
- [x] Admin can verify a pending doctor (Dr. Kabir Nair)
- [x] Admin access history shows both granted and denied attempts with reasons, filterable
- [x] Medical records can be filtered by type and date
- [x] Medical timeline renders in chronological (most recent first) order
- [x] "View" on every medical record opens its document (4 missing sample documents were added to `mockData.js`)
- [x] Doctor dashboard only shows the doctor's own patients; "Recently Accessed Patients" lists only granted accesses
- [x] Full test run: 116 of 116 test cases pass — see `TEST_CASES.md`
- [x] Patient can delete a document they uploaded themselves (after confirming); it disappears from Documents and its record from the records table
- [x] No Delete button appears on documents uploaded by doctors, or anywhere in the doctor or admin UI
