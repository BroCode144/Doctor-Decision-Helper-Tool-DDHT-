import { NavLink } from "react-router-dom";
import { Stethoscope, X } from "lucide-react";
import { NAV_CONFIG } from "./navConfig";

const ROLE_LABEL = {
  doctor: "Doctor Portal",
  patient: "Patient Portal",
  admin: "Admin Portal",
};

export default function Sidebar({ role, open, onClose }) {
  const links = NAV_CONFIG[role] || [];

  return (
    <>
      {open && (
        <div
          className="fixed inset-0 z-30 bg-ink-950/40 lg:hidden"
          onClick={onClose}
          aria-hidden="true"
        />
      )}
      <aside
        className={`fixed inset-y-0 left-0 z-40 flex w-64 flex-col border-r border-ink-100 bg-white transition-transform lg:static lg:translate-x-0 ${
          open ? "translate-x-0" : "-translate-x-full"
        }`}
      >
        <div className="flex items-center justify-between px-5 py-5">
          <div className="flex items-center gap-2.5">
            <div className="rounded-xl bg-brand-600 p-2 text-white">
              <Stethoscope size={20} />
            </div>
            <div>
              <p className="font-display text-base font-bold leading-tight text-ink-900">DDHT</p>
              <p className="text-[11px] font-medium text-ink-400">{ROLE_LABEL[role]}</p>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close navigation menu"
            className="rounded-lg p-1.5 text-ink-400 hover:bg-ink-100 lg:hidden"
          >
            <X size={18} />
          </button>
        </div>

        <nav className="flex-1 space-y-1 px-3 py-2" aria-label="Main navigation">
          {links.map(({ to, label, icon: Icon, end }) => (
            <NavLink
              key={to}
              to={to}
              end={end}
              onClick={onClose}
              className={({ isActive }) =>
                `flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium transition-colors ${
                  isActive
                    ? "bg-brand-50 text-brand-700"
                    : "text-ink-600 hover:bg-ink-50 hover:text-ink-900"
                }`
              }
            >
              <Icon size={18} className="shrink-0" />
              {label}
            </NavLink>
          ))}
        </nav>

        <div className="border-t border-ink-100 px-5 py-4">
          <p className="text-[11px] leading-relaxed text-ink-400">
            DDHT Prototype — Academic Demonstration Only. No AI, no real medical
            data.
          </p>
        </div>
      </aside>
    </>
  );
}
