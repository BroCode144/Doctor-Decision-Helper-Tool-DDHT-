import { useEffect, useState } from "react";
import { request } from "../lib/api";

/** Loads a stored file with the user's login (the server authorizes and logs the view)
    and returns a temporary in-browser URL for it. */
export function useFileUrl(documentId) {
  const [state, setState] = useState({ id: null, url: null, type: null, error: null });
  useEffect(() => {
    if (!documentId) return undefined;
    let url = null;
    let cancelled = false;
    request(`/documents/${documentId}/download`, { raw: true })
      .then((res) => res.blob())
      .then((blob) => {
        if (cancelled) return;
        url = URL.createObjectURL(blob);
        setState({ id: documentId, url, type: blob.type, error: null });
      })
      .catch((error) => !cancelled && setState({ id: documentId, url: null, type: null, error }));
    return () => {
      cancelled = true;
      if (url) URL.revokeObjectURL(url);
    };
  }, [documentId]);
  return state.id === documentId ? state : { url: null, type: null, error: null };
}
