import {
  LayoutDashboard,
  Search,
  ShieldCheck,
  User,
  FileText,
  Clock,
  ShieldQuestion,
  Users,
  BadgeCheck,
  History,
  UploadCloud,
} from "lucide-react";

export const NAV_CONFIG = {
  doctor: [
    { to: "/doctor", label: "Dashboard", icon: LayoutDashboard, end: true },
    { to: "/doctor/search", label: "Patient Search", icon: Search },
    { to: "/doctor/access-history", label: "My Access History", icon: History },
  ],
  patient: [
    { to: "/patient", label: "Dashboard", icon: LayoutDashboard, end: true },
    { to: "/patient/profile", label: "My Profile", icon: User },
    { to: "/patient/records", label: "My Medical Records", icon: FileText },
    { to: "/patient/timeline", label: "Medical Timeline", icon: Clock },
    { to: "/patient/upload", label: "Upload Record", icon: UploadCloud },
    { to: "/patient/consent", label: "Consent Management", icon: ShieldQuestion },
  ],
  admin: [
    { to: "/admin", label: "Dashboard", icon: LayoutDashboard, end: true },
    { to: "/admin/users", label: "User Management", icon: Users },
    { to: "/admin/doctors", label: "Doctor Verification", icon: BadgeCheck },
    { to: "/admin/access-history", label: "Access History", icon: ShieldCheck },
  ],
};
