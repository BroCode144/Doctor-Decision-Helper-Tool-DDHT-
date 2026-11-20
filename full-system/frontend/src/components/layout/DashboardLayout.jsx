import { useState } from "react";
import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { LogOut, Menu, Stethoscope, X } from "lucide-react";
import { useAuth } from "../../context/contexts";
import { initials } from "../../lib/format";
import { NAV_CONFIG, ROLE_TITLE } from "./navConfig";
import ThemeToggle from "./ThemeToggle";
import NotificationBell from "./NotificationBell";

const SIDEBAR_KEY = "ddht.sidebar";
const isWide = () => window.matchMedia("(min-width: 1024px)").matches; // Tailwind's lg breakpoint

function Sidebar({ role, open, collapsed, onClose, onCollapse }) {
  const links = NAV_CONFIG[role] || [];
  return (
    <>
      {open && <div className="fixed inset-0 z-30 bg-ink-950/40 lg:hidden" onClick={onClose} aria-hidden="true" />}
      {/* Wide screens: the panel slides shut by animating its width to 0 (the content inside keeps its width, so
          nothing squashes while it moves). Small screens: it slides in and out from the left as before. */}
      <aside
        id="main-sidebar"
        aria-hidden={collapsed && isWide() ? true : undefined}
        className={`fixed inset-y-0 left-0 z-40 flex w-64 shrink-0 flex-col overflow-hidden border-r border-ink-100 bg-white transition-[transform,width,visibility] duration-300 ease-in-out lg:static lg:translate-x-0
          ${open ? "translate-x-0" : "-translate-x-full"} ${collapsed ? "lg:invisible lg:w-0 lg:border-r-0" : "lg:w-64"}`}
      >
        <div className="flex h-full w-64 flex-col">
        <div className="flex items-center justify-between px-5 py-5">
          <div className="flex items-center gap-2.5">
            <div className="rounded-xl bg-brand-600 p-2 text-white">
              <Stethoscope size={20} />
            </div>
            <div>
              <p className="font-display text-base leading-tight font-bold text-ink-900">DDHT</p>
              <p className="text-[11px] font-medium text-ink-400">{ROLE_TITLE[role]}</p>
            </div>
          </div>
          <button type="button" onClick={onClose} aria-label="Close navigation menu" className="rounded-lg p-1.5 text-ink-400 hover:bg-ink-100 lg:hidden">
            <X size={18} />
          </button>
          <button type="button" onClick={onCollapse} aria-label="Hide the menu" title="Hide menu" aria-controls="main-sidebar"
            className="hidden rounded-lg p-2 text-ink-500 hover:bg-ink-100 lg:block">
            <Menu size={20} />
          </button>
        </div>
        <nav className="flex-1 space-y-0.5 overflow-y-auto px-3 py-2" aria-label="Main navigation">
          {links.map(({ to, label, icon: Icon, section, end }, i) => (
            <div key={to}>
              {section && section !== links[i - 1]?.section && (
                <p className="px-3 pt-4 pb-1.5 text-[11px] font-semibold tracking-wider text-ink-400 uppercase">{section}</p>
              )}
              <NavLink
                to={to}
                end={end || to.endsWith("/doctors")}
                onClick={onClose}
                className={({ isActive }) =>
                  `flex items-center gap-3 rounded-xl px-3 py-2 text-sm font-medium transition-colors ${isActive ? "bg-brand-50 text-brand-700" : "text-ink-600 hover:bg-ink-50 hover:text-ink-900"}`
                }
              >
                <Icon size={18} className="shrink-0" />
                {label}
              </NavLink>
            </div>
          ))}
        </nav>
        <div className="border-t border-ink-100 px-5 py-4">
          <p className="text-[11px] leading-relaxed text-ink-400">Fictional demo data only. AI output is drawn from records and is not medical advice.</p>
        </div>
        </div>
      </aside>
    </>
  );
}

export default function DashboardLayout() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [open, setOpen] = useState(false); // small screens: the slide-in menu
  // Wide screens: the ☰ button hides the left panel so the page gets the full width; remembered on this browser.
  const [collapsed, setCollapsed] = useState(() => {
    try { return localStorage.getItem(SIDEBAR_KEY) === "closed"; } catch { return false; }
  });
  const toggleMenu = () => {
    if (!isWide()) return setOpen(true);
    setCollapsed((c) => {
      try { localStorage.setItem(SIDEBAR_KEY, c ? "open" : "closed"); } catch { /* private mode: just don't remember */ }
      return !c;
    });
    return undefined;
  };

  const handleLogout = async () => {
    await logout();
    navigate("/login", { replace: true });
  };

  return (
    <div className="flex min-h-screen bg-ink-50">
      <Sidebar role={user?.role} open={open} collapsed={collapsed} onClose={() => setOpen(false)} onCollapse={toggleMenu} />
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-20 flex items-center justify-between gap-4 border-b border-ink-100 bg-white/90 px-4 py-3 backdrop-blur sm:px-6">
          <div className="flex items-center gap-3">
            {/* Opens the menu: always on small screens; on wide screens only while the panel is hidden (when it is
                open, its own ☰ next to "DDHT" closes it). */}
            <button type="button" onClick={toggleMenu} aria-controls="main-sidebar" title="Show menu"
              aria-label="Show the navigation menu" aria-expanded={false}
              className={`rounded-lg p-2 text-ink-500 hover:bg-ink-100 ${collapsed ? "" : "lg:hidden"}`}>
              <Menu size={20} />
            </button>
            <p className="font-display text-lg font-bold text-ink-900">{ROLE_TITLE[user?.role]}</p>
          </div>
          <div className="flex items-center gap-3">
            <div className="hidden text-right sm:block">
              <p className="text-sm font-semibold text-ink-800">{user?.full_name}</p>
              <p className="text-xs text-ink-400">
                {user?.role?.toLowerCase()} · {user?.patient_id || user?.doctor_id || user?.admin_id}
              </p>
            </div>
            <div className="flex h-9 w-9 items-center justify-center rounded-full bg-brand-100 text-sm font-bold text-brand-700" aria-hidden="true">
              {initials(user?.full_name) || "U"}
            </div>
            <ThemeToggle />
            <NotificationBell />
            <button type="button" onClick={handleLogout} className="inline-flex items-center gap-1.5 rounded-xl border border-ink-200 px-3 py-2 text-sm font-medium text-ink-600 hover:bg-ink-50">
              <LogOut size={16} />
              <span className="hidden sm:inline">Log out</span>
            </button>
          </div>
        </header>
        <main className="flex-1 px-4 py-6 sm:px-6 lg:px-8">
          <div className="mx-auto max-w-6xl">
            <Outlet />
          </div>
        </main>
        <footer className="border-t border-ink-100 px-4 py-4 text-center text-xs text-ink-400">
          DDHT Full System — fictional demo data. Not for real clinical use.
        </footer>
      </div>
    </div>
  );
}
