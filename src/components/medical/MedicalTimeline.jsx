import { formatDate } from "../../utils/dataHelpers";
import { typeIcon, typeTone } from "./recordMeta";
import EmptyState from "../ui/EmptyState";
import { Clock } from "lucide-react";

export default function MedicalTimeline({ events }) {
  if (!events || events.length === 0) {
    return <EmptyState icon={Clock} message="No medical timeline events available." />;
  }

  return (
    <ol className="relative space-y-6 border-l-2 border-ink-100 pl-6">
      {events.map((event) => {
        const Icon = typeIcon(event.type);
        return (
          <li key={event.id} className="relative">
            <span
              className={`absolute -left-[31px] flex h-7 w-7 items-center justify-center rounded-full ring-4 ring-ink-50 ${typeTone(event.type)}`}
            >
              <Icon size={14} />
            </span>
            <div className="rounded-2xl border border-ink-100 bg-white p-4 shadow-sm">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <p className="text-xs font-semibold uppercase tracking-wide text-brand-600">
                  {event.type}
                </p>
                <p className="text-xs font-medium text-ink-400">{formatDate(event.date)}</p>
              </div>
              <p className="mt-1 font-semibold text-ink-900">{event.title}</p>
              <p className="mt-1 text-sm text-ink-500">
                {event.doctor}
                {event.hospital ? ` · ${event.hospital}` : ""}
              </p>
              {event.description && (
                <p className="mt-2 text-sm leading-relaxed text-ink-600">{event.description}</p>
              )}
            </div>
          </li>
        );
      })}
    </ol>
  );
}
