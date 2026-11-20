import { Navigate, Outlet, Route, Routes } from "react-router-dom";
import { useAuth } from "./context/contexts";
import DashboardLayout from "./components/layout/DashboardLayout";
import { ROLE_HOME } from "./components/layout/navConfig";
import { Loading } from "./components/ui";
import LoginPage from "./pages/LoginPage";

import PatientDashboard from "./pages/patient/PatientDashboard";
import PatientProfile from "./pages/patient/PatientProfile";
import PatientRecords from "./pages/patient/PatientRecords";
import PatientTimeline from "./pages/patient/PatientTimeline";
import PatientDocuments from "./pages/patient/PatientDocuments";
import PatientUpload from "./pages/patient/PatientUpload";
import PatientConsent from "./pages/patient/PatientConsent";
import AccessLogPage from "./pages/AccessLogPage";
import AppointmentsPage from "./pages/appointments/AppointmentsPage";
import BookAppointment from "./pages/patient/BookAppointment";
import BookingDetails from "./pages/patient/BookingDetails";
import PatientTestReports from "./pages/patient/PatientTestReports";
import PatientMedicines from "./pages/patient/PatientMedicines";
import DoctorAvailability from "./pages/doctor/DoctorAvailability";

import DoctorDashboard from "./pages/doctor/DoctorDashboard";
import DoctorPatients from "./pages/doctor/DoctorPatients";
import PatientWorkspace from "./pages/doctor/PatientWorkspace";
import * as W from "./pages/doctor/WorkspaceTabs";
import DoctorAI from "./pages/doctor/DoctorAI";
import DoctorCompare from "./pages/doctor/DoctorCompare";
import { DecisionSupportPage } from "./features/decision-support";

import AdminDashboard from "./pages/admin/AdminDashboard";
import AdminUsers from "./pages/admin/AdminUsers";
import AdminDoctors from "./pages/admin/AdminDoctors";
import AdminVerification from "./pages/admin/AdminVerification";
import AdminUploads from "./pages/admin/AdminUploads";
import AdminLocalDiseases from "./pages/admin/AdminLocalDiseases";
import ReceptionDashboard from "./pages/reception/ReceptionDashboard";
import * as Onboarding from "./features/doctor-onboarding";
import PatientHealthBackground from "./pages/patient/PatientHealthBackground";

/** Client-side guard for UX only — the backend enforces every permission. */
function Protected({ roles }) {
  const { user, ready } = useAuth();
  if (!ready) return <Loading label="Restoring session…" />;
  if (!user) return <Navigate to="/login" replace />;
  if (!roles.includes(user.role)) return <Navigate to={ROLE_HOME[user.role]} replace />;
  return <Outlet />;
}

function Home() {
  const { user, ready } = useAuth();
  if (!ready) return <Loading />;
  return <Navigate to={user ? ROLE_HOME[user.role] : "/login"} replace />;
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/doctor/apply" element={<Onboarding.DoctorApply />} />
      <Route path="/doctor/application-status" element={<Onboarding.ApplicationStatus />} />
      <Route path="/doctor/reupload" element={<Onboarding.Reupload />} />
      <Route path="/set-password" element={<Onboarding.SetPassword />} />
      <Route path="/" element={<Home />} />

      <Route element={<Protected roles={["PATIENT"]} />}>
        <Route path="/patient" element={<DashboardLayout />}>
          <Route index element={<Navigate to="dashboard" replace />} />
          <Route path="dashboard" element={<PatientDashboard />} />
          <Route path="profile" element={<PatientProfile />} />
          <Route path="health-background" element={<PatientHealthBackground />} />
          <Route path="records" element={<PatientRecords />} />
          <Route path="test-reports" element={<PatientTestReports />} />
          <Route path="medicines" element={<PatientMedicines />} />
          <Route path="timeline" element={<PatientTimeline />} />
          <Route path="documents" element={<PatientDocuments />} />
          <Route path="upload" element={<PatientUpload />} />
          <Route path="consent" element={<PatientConsent />} />
          <Route path="appointments" element={<AppointmentsPage />} />
          <Route path="appointments/book" element={<BookAppointment />} />
          <Route path="appointments/book/details" element={<BookingDetails />} />
          <Route path="access-log" element={<AccessLogPage scope="patient" />} />
        </Route>
      </Route>

      <Route element={<Protected roles={["DOCTOR"]} />}>
        <Route path="/doctor" element={<DashboardLayout />}>
          <Route index element={<Navigate to="dashboard" replace />} />
          <Route path="dashboard" element={<DoctorDashboard />} />
          <Route path="patients" element={<DoctorPatients />} />
          <Route path="patients/:patientId" element={<PatientWorkspace />}>
            <Route index element={<W.OverviewTab />} />
            <Route path="history" element={<W.HistoryTab />} />
            <Route path="timeline" element={<W.TimelineTab />} />
            <Route path="records" element={<W.RecordsTab />} />
            <Route path="documents" element={<W.DocumentsTab />} />
            <Route path="diagnoses" element={<W.DiagnosesTab />} />
            <Route path="prescriptions" element={<W.PrescriptionsTab />} />
            <Route path="consultations" element={<W.ConsultationsTab />} />
            <Route path="upload" element={<W.UploadTab />} />
            <Route path="ai" element={<DoctorAI />} />
            <Route path="compare" element={<DoctorCompare />} />
            <Route path="decision" element={<DecisionSupportPage />} />
          </Route>
          <Route path="access-history" element={<AccessLogPage scope="doctor" />} />
          <Route path="appointments" element={<AppointmentsPage />} />
          <Route path="availability" element={<DoctorAvailability />} />
        </Route>
      </Route>

      <Route element={<Protected roles={["ADMIN"]} />}>
        <Route path="/admin" element={<DashboardLayout />}>
          <Route index element={<Navigate to="dashboard" replace />} />
          <Route path="dashboard" element={<AdminDashboard />} />
          <Route path="users" element={<AdminUsers />} />
          <Route path="doctors" element={<AdminDoctors />} />
          <Route path="doctors/verification" element={<AdminVerification />} />
          <Route path="doctor-applications" element={<Onboarding.AdminDoctorApplications />} />
          <Route path="uploads" element={<AdminUploads />} />
          <Route path="access-history" element={<AccessLogPage scope="admin" />} />
          <Route path="local-diseases" element={<AdminLocalDiseases />} />
        </Route>
      </Route>

      <Route element={<Protected roles={["RECEPTION"]} />}>
        <Route path="/reception" element={<DashboardLayout />}>
          <Route index element={<Navigate to="dashboard" replace />} />
          <Route path="dashboard" element={<ReceptionDashboard />} />
        </Route>
      </Route>

      <Route path="*" element={<Home />} />
    </Routes>
  );
}
