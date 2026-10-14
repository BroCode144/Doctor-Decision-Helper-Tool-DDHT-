import { useNavigate } from "react-router-dom";
import { Menu, LogOut } from "lucide-react";
import { useAuth } from "../../context/AuthContext";

const ROLE_LABEL = {
  doctor: "Doctor",
  patient: "Patient",
  admin: "Administrator",
};

export default function Header({ title, subtitle, onMenuClick }) {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  const handleLogout = () => {
    logout();
    navigate("/login", { replace: true });
  };

  const initials = (user?.name || "")
    .split(" ")
    .map((w) => w[0])
    .slice(0, 2)
    .join("")
    .toUpperCase();

  return (
    <header className="sticky top-0 z-20 flex items-center justify-between gap-4 border-b border-ink-100 bg-white/90 px-4 py-4 backdrop-blur sm:px-6">
      <div className="flex items-center gap-3">
        <button
          type="button"
          onClick={onMenuClick}
          aria-label="Open navigation menu"
          className="rounded-lg p-2 text-ink-500 hover:bg-ink-100 lg:hidden"
        >
          <Menu size={20} />
        </button>
        <div>
          <h1 className="font-display text-lg font-bold text-ink-900 sm:text-xl">{title}</h1>
          {subtitle && <p className="text-sm text-ink-500">{subtitle}</p>}
        </div>
      </div>

      <div className="flex items-center gap-3">
        <div className="hidden text-right sm:block">
          <p className="text-sm font-semibold text-ink-800">{user?.name}</p>
          <p className="text-xs text-ink-400">{ROLE_LABEL[user?.role]}</p>
        </div>
        <div
          className="flex h-9 w-9 items-center justify-center rounded-full bg-brand-100 text-sm font-bold text-brand-700"
          aria-hidden="true"
        >
          {initials || "U"}
        </div>
        <button
          type="button"
          onClick={handleLogout}
          className="inline-flex items-center gap-1.5 rounded-xl border border-ink-200 px-3 py-2 text-sm font-medium text-ink-600 hover:bg-ink-50"
        >
          <LogOut size={16} />
          <span className="hidden sm:inline">Log out</span>
        </button>
      </div>
    </header>
  );
}
