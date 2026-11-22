// Doctor applications: multipart calls (the public ones need no sign-in), and reading the emailed one-time token.
import { ApiError, getToken } from "../../lib/api";

/** POST a FormData to /api{path}; returns the JSON body or throws ApiError. */
export async function postForm(path, formData) {
  let res;
  try {
    res = await fetch(`/api${path}`, { method: "POST", body: formData });
  } catch {
    throw new ApiError(0, "Cannot reach the DDHT server. Check that the backend is running.");
  }
  let body = null;
  try {
    body = await res.json();
  } catch {
    /* non-JSON */
  }
  if (!res.ok) throw new ApiError(res.status, body?.detail || "Request failed.");
  return body;
}

/** Open an application file for the admin (signed in) in a new tab. */
export async function openApplicationFile(appId, docId) {
  const win = window.open("", "_blank");
  try {
    const res = await fetch(`/api/admin/doctor-applications/${appId}/documents/${docId}`, {
      headers: { Authorization: `Bearer ${getToken()}` },
    });
    if (!res.ok) {
      const body = await res.json().catch(() => null);
      throw new ApiError(res.status, body?.detail || "Could not open the file.");
    }
    const url = URL.createObjectURL(await res.blob());
    if (win) win.location.href = url;
    setTimeout(() => URL.revokeObjectURL(url), 60_000);
  } catch (e) {
    win?.close();
    throw e;
  }
}

/** The token sits after '#' in emailed links (#token=...), so it is never sent to the server in the URL. */
export function tokenFromHash() {
  const m = /token=([\w-]+)/.exec(window.location.hash || "");
  return m ? m[1] : "";
}

export const MAX_MB = 10;
export const ACCEPT = ".pdf,.png,.jpg,.jpeg,application/pdf,image/png,image/jpeg";

export const STATUS_LABEL = {
  CHECKING: { label: "Checking documents", variant: "pending" },
  UNDER_REVIEW: { label: "Waiting for review", variant: "pending" },
  NEEDS_INFO: { label: "Needs a document", variant: "warning" },
  APPROVED: { label: "Approved", variant: "success" },
  REJECTED: { label: "Not approved", variant: "danger" },
};
