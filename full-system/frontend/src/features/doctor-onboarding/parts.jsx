import { Link } from "react-router-dom";
import { FileCheck2, Stethoscope, Upload } from "lucide-react";
import { ACCEPT, MAX_MB } from "./api";
import { MovingBackground } from "../auth/DotField";

/** Simple frame for the public doctor pages (no sign-in). */
export function PublicShell({ title, subtitle, children, wide = false }) {
  return (
    <div className="relative min-h-screen overflow-hidden bg-[#0b1430] px-4 py-8 sm:py-12">
      <MovingBackground />
      <div className={`relative mx-auto w-full ${wide ? "max-w-3xl" : "max-w-lg"}`}>
        <Link to="/login" className="animate-rise-in mb-5 inline-flex items-center gap-2.5 text-white">
          <span className="rounded-xl bg-white/10 p-2 ring-1 ring-white/20 backdrop-blur"><Stethoscope size={18} /></span>
          <span className="font-display text-lg font-bold tracking-wide">DDHT</span>
        </Link>
        <div className="animate-rise-in rounded-3xl bg-white p-6 shadow-[0_30px_80px_-20px_rgba(0,0,0,0.55)] ring-1 ring-white/20 sm:p-8" style={{ "--delay": "100ms" }}>
          <h1 className="font-display text-2xl font-bold text-ink-900">{title}</h1>
          {subtitle && <p className="mt-1 text-sm text-ink-500">{subtitle}</p>}
          <div className="mt-6">{children}</div>
        </div>
        <p className="mt-4 text-center text-xs text-slate-400">Fictional demo data only. Not for real clinical use.</p>
      </div>
    </div>
  );
}

/** One required/optional document: label, hint, chosen file. */
export function FileField({ label, hint, required, file, onChange, invalid }) {
  return (
    <label className={`flex cursor-pointer items-center gap-3 rounded-xl border p-3 transition ${invalid ? "border-amber-300 bg-amber-50" : file ? "border-green-200 bg-green-50/50" : "border-ink-200 hover:border-brand-300"}`}>
      <span className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-lg ${file ? "bg-green-100 text-green-700" : "bg-ink-100 text-ink-500"}`}>
        {file ? <FileCheck2 size={18} /> : <Upload size={18} />}
      </span>
      <span className="min-w-0 flex-1">
        <span className="block text-sm font-semibold text-ink-800">{label}{required && <span className="text-red-600"> *</span>}</span>
        <span className="block truncate text-xs text-ink-500">{file ? `${file.name} · ${(file.size / 1048576).toFixed(1)} MB` : hint || `PDF, PNG or JPEG, up to ${MAX_MB} MB`}</span>
      </span>
      <input type="file" accept={ACCEPT} className="sr-only" onChange={(e) => onChange(e.target.files?.[0] || null)} />
    </label>
  );
}
