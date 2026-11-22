import {
  FileCheck2,
  Activity,
  CalendarClock,
  CalendarPlus,
  Eye,
  FlaskConical,
  House,
  Pill,
  CalendarDays,
  ClipboardPlus,
  HeartPulse,
  MapPin,
  BadgeCheck,
  FileText,
  FolderOpen,
  History,
  LayoutDashboard,
  Search,
  ShieldCheck,
  ShieldQuestion,
  Stethoscope,
  UploadCloud,
  User,
  Users,
} from "lucide-react";

export const NAV_CONFIG = {
  // Plain-language labels, grouped so patients can find things quickly.
  PATIENT: [
    { to: "/patient/dashboard", label: "Home", icon: House },
    { section: "Visits", to: "/patient/appointments", label: "My appointments", icon: CalendarClock, end: true },
    { section: "Visits", to: "/patient/appointments/book", label: "Book an appointment", icon: CalendarPlus },
    { section: "My health", to: "/patient/test-reports", label: "Test reports", icon: FlaskConical },
    { section: "My health", to: "/patient/medicines", label: "Medicines", icon: Pill },
    { section: "My health", to: "/patient/records", label: "All health records", icon: FileText },
    { section: "My health", to: "/patient/timeline", label: "Health timeline", icon: Activity },
    { section: "My health", to: "/patient/documents", label: "My documents", icon: FolderOpen },
    { section: "My health", to: "/patient/upload", label: "Upload a document", icon: UploadCloud },
    { section: "Privacy", to: "/patient/consent", label: "Doctor access", icon: ShieldQuestion },
    { section: "Privacy", to: "/patient/access-log", label: "Who viewed my records", icon: Eye },
    { section: "Account", to: "/patient/profile", label: "My profile", icon: User },
    { section: "Account", to: "/patient/health-background", label: "Allergies & history", icon: HeartPulse },
  ],
  DOCTOR: [
    { to: "/doctor/dashboard", label: "Dashboard", icon: LayoutDashboard },
    { to: "/doctor/patients", label: "Patients", icon: Search },
    { section: "Consultations", to: "/doctor/appointments", label: "Appointments", icon: CalendarClock },
    { section: "Consultations", to: "/doctor/availability", label: "Availability", icon: CalendarDays },
    { section: "Audit", to: "/doctor/access-history", label: "My access history", icon: History },
  ],
  ADMIN: [
    { to: "/admin/dashboard", label: "Dashboard", icon: LayoutDashboard },
    { to: "/admin/users", label: "Users", icon: Users },
    { to: "/admin/doctors", label: "Doctors & Visits", icon: Stethoscope },
    { to: "/admin/doctors/verification", label: "Doctor Verification", icon: BadgeCheck },
    { to: "/admin/doctor-applications", label: "Doctor applications", icon: FileCheck2 },
    { to: "/admin/uploads", label: "Uploads", icon: UploadCloud },
    { to: "/admin/access-history", label: "Access History", icon: ShieldCheck },
    { to: "/admin/local-diseases", label: "Local diseases", icon: MapPin },
  ],
  RECEPTION: [
    { to: "/reception/dashboard", label: "Today's check-in", icon: ClipboardPlus },
  ],
};

export const ROLE_HOME = { PATIENT: "/patient/dashboard", DOCTOR: "/doctor/dashboard", ADMIN: "/admin/dashboard", RECEPTION: "/reception/dashboard" };
export const ROLE_TITLE = { PATIENT: "Patient Portal", DOCTOR: "Doctor Workspace", ADMIN: "Admin Console", RECEPTION: "Reception" };
