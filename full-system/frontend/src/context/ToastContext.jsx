import { useCallback, useMemo, useRef, useState } from "react";
import { CheckCircle2, Info, X, XCircle } from "lucide-react";
import { ToastContext } from "./contexts";

const ICONS = { success: CheckCircle2, error: XCircle, info: Info };
const STYLES = {
  success: "bg-green-600 text-white",
  error: "bg-red-600 text-white",
  info: "bg-slate-800 text-white",
};

export function ToastProvider({ children }) {
  const [toasts, setToasts] = useState([]);
  const counter = useRef(0);

  const dismiss = useCallback((id) => setToasts((prev) => prev.filter((t) => t.id !== id)), []);

  const showToast = useCallback(
    (message, type = "info") => {
      const id = ++counter.current;
      setToasts((prev) => [...prev, { id, message, type }]);
      setTimeout(() => dismiss(id), 5000);
    },
    [dismiss]
  );

  const value = useMemo(() => ({ showToast }), [showToast]);

  return (
    <ToastContext.Provider value={value}>
      {children}
      <div className="fixed top-4 right-4 z-[100] flex w-[min(92vw,380px)] flex-col gap-2" aria-live="polite">
        {toasts.map((toast) => {
          const Icon = ICONS[toast.type] || Info;
          return (
            <div
              key={toast.id}
              role="status"
              className={`animate-toast-in flex items-start gap-3 rounded-xl px-4 py-3 shadow-lg ${STYLES[toast.type] || STYLES.info}`}
            >
              <Icon size={18} className="mt-0.5 shrink-0" />
              <p className="text-sm font-medium leading-snug">{toast.message}</p>
              <button type="button" onClick={() => dismiss(toast.id)} aria-label="Dismiss notification" className="ml-auto shrink-0 opacity-80 hover:opacity-100">
                <X size={16} />
              </button>
            </div>
          );
        })}
      </div>
    </ToastContext.Provider>
  );
}
