export default function FilterBar({ filters }) {
  return (
    <div className="flex flex-wrap items-center gap-3">
      {filters.map((filter) => (
        <div key={filter.label} className="flex flex-col gap-1">
          <label htmlFor={`filter-${filter.label}`} className="text-xs font-medium text-ink-500">
            {filter.label}
          </label>
          {filter.type === "date" ? (
            <input
              id={`filter-${filter.label}`}
              type="date"
              value={filter.value}
              onChange={(e) => filter.onChange(e.target.value)}
              className="rounded-lg border border-ink-200 bg-white px-3 py-2 text-sm text-ink-800 focus:border-brand-400 focus:outline-none focus:ring-2 focus:ring-brand-100"
            />
          ) : (
            <select
              id={`filter-${filter.label}`}
              value={filter.value}
              onChange={(e) => filter.onChange(e.target.value)}
              className="rounded-lg border border-ink-200 bg-white px-3 py-2 text-sm text-ink-800 focus:border-brand-400 focus:outline-none focus:ring-2 focus:ring-brand-100"
            >
              {filter.options.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
          )}
        </div>
      ))}
    </div>
  );
}
