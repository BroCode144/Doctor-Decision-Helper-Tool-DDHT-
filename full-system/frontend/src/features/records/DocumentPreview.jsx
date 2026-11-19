import { AlertTriangle, ExternalLink, FileText, Loader2 } from "lucide-react";
import { useFileUrl } from "../../hooks/useFileUrl";

/** Shows the actual document: PDFs in the browser's PDF viewer, images inline. */
export default function DocumentPreview({ documentId, title, height = "70vh" }) {
  const { url, type, error } = useFileUrl(documentId);
  if (error) {
    return (
      <div className="flex items-center gap-2 rounded-xl bg-red-50 p-4 text-sm text-red-800">
        <AlertTriangle size={18} className="shrink-0" /> {error.message || "The file could not be loaded."}
      </div>
    );
  }
  if (!url) {
    return (
      <div className="flex items-center justify-center gap-2 rounded-xl bg-ink-50 text-sm text-ink-500" style={{ height: 240 }}>
        <Loader2 size={18} className="animate-spin text-brand-600" /> Loading the document…
      </div>
    );
  }
  const openButton = (
    <a href={url} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1.5 text-sm font-semibold text-brand-700 hover:underline">
      <ExternalLink size={15} /> Open full screen
    </a>
  );
  if (type?.startsWith("image/")) {
    return (
      <div className="space-y-2">
        <img src={url} alt={title || "Document"} className="mx-auto max-h-[70vh] rounded-xl border border-ink-100 object-contain" />
        <div className="text-right">{openButton}</div>
      </div>
    );
  }
  if (type === "application/pdf") {
    return (
      <div className="space-y-2">
        <iframe src={url} title={title || "Document"} className="w-full rounded-xl border border-ink-100 bg-ink-50" style={{ height }} />
        <div className="flex items-center justify-between gap-3 text-xs text-ink-400">
          <span>Can&apos;t see it on your phone? Use Open full screen.</span>
          {openButton}
        </div>
      </div>
    );
  }
  return (
    <div className="flex flex-col items-center gap-3 rounded-xl bg-ink-50 p-8 text-center text-sm text-ink-600">
      <FileText size={28} className="text-ink-400" />
      This file type can&apos;t be shown here.
      {openButton}
    </div>
  );
}
