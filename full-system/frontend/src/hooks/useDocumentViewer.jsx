import { useState } from "react";
import { DocumentViewer } from "../features/records";

/** Returns [viewerElement, openDocument(id)] for the shared document modal. */
export function useDocumentViewer() {
  const [docId, setDocId] = useState(null);
  const viewer = <DocumentViewer documentId={docId} onClose={() => setDocId(null)} />;
  return [viewer, setDocId];
}
