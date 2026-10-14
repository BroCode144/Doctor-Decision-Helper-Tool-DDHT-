import { Loader2 } from "lucide-react";

export default function Loading({ message = "Loading..." }) {
  return (
    <div className="flex flex-col items-center justify-center gap-3 py-16 text-ink-400">
      <Loader2 size={26} className="animate-spin text-brand-500" />
      <p className="text-sm font-medium">{message}</p>
    </div>
  );
}
