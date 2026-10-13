import { Routes, Route, Navigate } from "react-router-dom";
import { useAuth } from "./context/AuthContext";
import ProtectedRoute from "./components/ui/ProtectedRoute";
import DashboardLayout from "./components/layout/DashboardLayout";

import LoginPage from "./pages/LoginPage";

import DoctorDashboard from "./pages/doctor/DoctorDashboard";
import PatientSearchPage from "./pages/doctor/PatientSearchPage";
import DoctorAccessHistoryPage from "./pages/doctor/DoctorAccessHistoryPage";

import PatientDashboard from "./pages/patient/PatientDashboard";
import MyProfilePage from "./pages/patient/MyProfilePage";
import MyRecordsPage from "./pages/patient/MyRecordsPage";
import MyTimelinePage from "./pages/patient/MyTimelinePage";
import UploadRecordPage from "./pages/patient/UploadRecordPage";
import ConsentManagementPage from "./pages/patient/ConsentManagementPage";

import AdminDashboard from "./pages/admin/AdminDashboard";
import UserManagementPage from "./pages/admin/UserManagementPage";
import DoctorVerificationPage from "./pages/admin/DoctorVerificationPage";
import AccessHistoryPage from "./pages/admin/AccessHistoryPage";

const ROLE_HOME = { doctor: "/doctor", patient: "/patient", admin: "/admin" };

function RootRedirect() {
  const { user } = useAuth();
  if (!user) return <Navigate to="/login" replace />;
  return <Navigate to={ROLE_HOME[user.role] || "/login"} replace />;
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/" element={<RootRedirect />} />

      <Route element={<ProtectedRoute allowedRoles={["doctor"]} />}>
        <Route path="/doctor" element={<DashboardLayout />}>
          <Route index element={<DoctorDashboard />} />
          <Route path="search" element={<PatientSearchPage />} />
          <Route path="access-history" element={<DoctorAccessHistoryPage />} />
        </Route>
      </Route>

      <Route element={<ProtectedRoute allowedRoles={["patient"]} />}>
        <Route path="/patient" element={<DashboardLayout />}>
          <Route index element={<PatientDashboard />} />
          <Route path="profile" element={<MyProfilePage />} />
          <Route path="records" element={<MyRecordsPage />} />
          <Route path="timeline" element={<MyTimelinePage />} />
          <Route path="upload" element={<UploadRecordPage />} />
          <Route path="consent" element={<ConsentManagementPage />} />
        </Route>
      </Route>

      <Route element={<ProtectedRoute allowedRoles={["admin"]} />}>
        <Route path="/admin" element={<DashboardLayout />}>
          <Route index element={<AdminDashboard />} />
          <Route path="users" element={<UserManagementPage />} />
          <Route path="doctors" element={<DoctorVerificationPage />} />
          <Route path="access-history" element={<AccessHistoryPage />} />
        </Route>
      </Route>

      <Route path="*" element={<RootRedirect />} />
    </Routes>
  );
}
