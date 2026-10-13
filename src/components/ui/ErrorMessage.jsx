import { AlertTriangle } from "lucide-react";

export default function ErrorMessage({ title = "Something went wrong", message, children }) {
  return (
    <div
      role="alert"
      className="flex items-start gap-3 rounded-xl border border-rose-200 bg-rose-50 px-4 py-3"
    >
      <AlertTriangle size={18} className="mt-0.5 shrink-0 text-rose-600" />
      <div>
        <p className="text-sm font-semibold text-rose-800">{title}</p>
        {message && <p className="mt-0.5 text-sm text-rose-700">{message}</p>}
        {children}
      </div>
    </div>
  );
}
