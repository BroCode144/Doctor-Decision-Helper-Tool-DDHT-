import { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Bell, CalendarCheck, CalendarClock, CalendarX, CheckCheck, CheckCircle2, ShieldCheck, ShieldQuestion, ShieldX, UserX } from "lucide-react";

const KIND_ICON = {
  APPOINTMENT_REQUESTED: [CalendarClock, "text-sky-700 bg-sky-50"],
  APPOINTMENT_CONFIRMED: [CalendarCheck, "text-green-700 bg-green-50"],
  APPOINTMENT_RESCHEDULED: [CalendarClock, "text-amber-700 bg-amber-50"],
  APPOINTMENT_CANCELLED: [CalendarX, "text-red-700 bg-red-50"],
  CONSENT_REQUESTED: [ShieldQuestion, "text-amber-700 bg-amber-50"],
  CONSENT_APPROVED: [ShieldCheck, "text-green-700 bg-green-50"],
  CONSENT_DECLINED: [ShieldX, "text-red-700 bg-red-50"],
  CONSULTATION_COMPLETED: [CheckCircle2, "text-green-700 bg-green-50"],
  CONSULTATION_NO_SHOW: [UserX, "text-amber-700 bg-amber-50"],
};
import { api } from "../../lib/api";
import { relative } from "../../lib/time";

const POLL_MS = 30_000;

/** In-app notifications. They hold no clinical details, only a title and a link into the portal. */
export default function NotificationBell() {
  const navigate = useNavigate();
  const [data, setData] = useState({ unread: 0, items: [] });
  const [open, setOpen] = useState(false);
  const [now, setNow] = useState(() => Date.now());
  const box = useRef(null);

  const load = useCallback(() => {
    api.get("/notifications", { limit: 15 }).then((d) => { setData(d); setNow(Date.now()); }).catch(() => {});
  }, []);

  useEffect(() => {
    load();
    const t = setInterval(load, POLL_MS);
    return () => clearInterval(t);
  }, [load]);

  useEffect(() => {
    if (!open) return undefined;
    const close = (e) => { if (box.current && !box.current.contains(e.target)) setOpen(false); };
    document.addEventListener("mousedown", close);
    return () => document.removeEventListener("mousedown", close);
  }, [open]);

  const openItem = async (n) => {
    setOpen(false);
    if (!n.read) await api.post(`/notifications/${n.id}/read`).catch(() => {});
    load();
    if (n.link) navigate(n.link);
  };

  const readAll = async () => {
    await api.post("/notifications/read-all").catch(() => {});
    load();
  };

  return (
    <div className="relative" ref={box}>
      <button type="button" onClick={() => { setOpen((o) => !o); load(); }} aria-label={`Notifications${data.unread ? `, ${data.unread} unread` : ""}`}
        className="relative rounded-xl border border-ink-200 p-2 text-ink-600 hover:bg-ink-50">
        <Bell size={18} />
        {data.unread > 0 && (
          <span className="absolute -top-1.5 -right-1.5 flex h-5 min-w-5 items-center justify-center rounded-full bg-red-600 px-1 text-[11px] font-bold text-white">
            {data.unread > 9 ? "9+" : data.unread}
          </span>
        )}
      </button>
      {open && (
        <div className="absolute right-0 z-40 mt-2 w-[min(92vw,360px)] overflow-hidden rounded-2xl border border-ink-100 bg-white shadow-xl">
          <div className="flex items-center justify-between border-b border-ink-100 px-4 py-3">
            <p className="font-display text-sm font-bold text-ink-900">Notifications</p>
            {data.unread > 0 && (
              <button type="button" onClick={readAll} className="inline-flex items-center gap-1 text-xs font-semibold text-brand-700 hover:underline">
                <CheckCheck size={14} /> Mark all read
              </button>
            )}
          </div>
          <ul className="max-h-96 divide-y divide-ink-100 overflow-y-auto">
            {data.items.length === 0 && <li className="px-4 py-6 text-center text-sm text-ink-500">No notifications yet.</li>}
            {data.items.map((n) => {
              const [Icon, tone] = KIND_ICON[n.kind] || [Bell, "text-ink-600 bg-ink-100"];
              return (
              <li key={n.id}>
                <button type="button" onClick={() => openItem(n)} className={`flex w-full gap-3 px-4 py-3 text-left hover:bg-ink-50 ${n.read ? "" : "bg-brand-50/50"}`}>
                  <span className={`relative mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-lg ${tone}`}>
                    <Icon size={16} />
                    {!n.read && <span className="absolute -top-0.5 -right-0.5 h-2.5 w-2.5 rounded-full bg-brand-600 ring-2 ring-white" aria-label="Unread" />}
                  </span>
                  <span className="min-w-0">
                    <span className="block text-sm font-semibold text-ink-900">{n.title}</span>
                    {n.body && <span className="block text-xs text-ink-600">{n.body}</span>}
                    <span className="block text-[11px] text-ink-400">{relative(n.created_at, now)}</span>
                  </span>
                </button>
              </li>
              );
            })}
          </ul>
        </div>
      )}
    </div>
  );
}
