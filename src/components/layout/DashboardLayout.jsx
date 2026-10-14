import { useState } from "react";
import { Outlet } from "react-router-dom";
import { useAuth } from "../../context/AuthContext";
import Sidebar from "./Sidebar";
import Header from "./Header";

const ROLE_TITLE = {
  doctor: "Doctor Workspace",
  patient: "Patient Portal",
  admin: "Admin Console",
};

export default function DashboardLayout() {
  const { user } = useAuth();
  const [sidebarOpen, setSidebarOpen] = useState(false);

  return (
    <div className="flex min-h-screen bg-ink-50">
      <Sidebar role={user?.role} open={sidebarOpen} onClose={() => setSidebarOpen(false)} />
      <div className="flex min-w-0 flex-1 flex-col">
        <Header
          title={ROLE_TITLE[user?.role] || "DDHT"}
          onMenuClick={() => setSidebarOpen(true)}
        />
        <main className="flex-1 px-4 py-6 sm:px-6 lg:px-8">
          <div className="mx-auto max-w-6xl">
            <Outlet />
          </div>
        </main>
        <footer className="border-t border-ink-100 px-4 py-4 text-center text-xs text-ink-400 sm:px-6">
          DDHT Prototype — Academic Demonstration Only. Not for real clinical use.
        </footer>
      </div>
    </div>
  );
}
