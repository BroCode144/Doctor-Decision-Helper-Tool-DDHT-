import { Inbox } from "lucide-react";

export default function EmptyState({ icon: Icon = Inbox, message = "Nothing here yet.", hint, action }) {
  return (
    <div className="flex flex-col items-center justify-center gap-2 rounded-2xl border border-dashed border-ink-200 bg-ink-50/40 px-6 py-14 text-center">
      <div className="rounded-full bg-ink-100 p-3 text-ink-400">
        <Icon size={22} />
      </div>
      <p className="font-medium text-ink-600">{message}</p>
      {hint && <p className="max-w-sm text-sm text-ink-400">{hint}</p>}
      {action && <div className="mt-2">{action}</div>}
    </div>
  );
}
