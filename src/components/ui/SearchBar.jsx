import { Search } from "lucide-react";

export default function SearchBar({ value, onChange, placeholder = "Search...", label }) {
  return (
    <div className="relative w-full">
      {label && (
        <label htmlFor="search-input" className="sr-only">
          {label}
        </label>
      )}
      <Search
        size={17}
        className="pointer-events-none absolute left-3.5 top-1/2 -translate-y-1/2 text-ink-400"
      />
      <input
        id="search-input"
        type="text"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        className="w-full rounded-xl border border-ink-200 bg-white py-2.5 pl-10 pr-4 text-sm text-ink-900 placeholder:text-ink-400 focus:border-brand-400 focus:outline-none focus:ring-2 focus:ring-brand-100"
      />
    </div>
  );
}
