// Thin client for the DDHT FastAPI backend. All authorization decisions are
// made by the backend; the frontend only displays what the API returns.

const BASE = "/api";
const TOKEN_KEY = "ddht.token";

export class ApiError extends Error {
  constructor(status, detail) {
    const d = detail && typeof detail === "object" ? detail : { message: String(detail || "") };
    super(d.message || "Request failed.");
    this.status = status;
    this.code = d.code;
    this.reason = d.reason;
    this.access = d.access;
    this.fields = d.fields;
    this.detail = d; // any extra fields the server sent (e.g. email, email_sent)
  }

  get isAccessDenied() {
    return this.status === 403 && this.code === "ACCESS_DENIED";
  }
}

export function getToken() {
  try {
    return sessionStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
}

export function setToken(token) {
  try {
    if (token) sessionStorage.setItem(TOKEN_KEY, token);
    else sessionStorage.removeItem(TOKEN_KEY);
  } catch {
    /* storage unavailable: session lasts for this page only */
  }
}

let onUnauthorized = () => {};
export function setUnauthorizedHandler(fn) {
  onUnauthorized = fn;
}

function friendly(status) {
  if (status === 0) return "Cannot reach the DDHT server. Check that the backend is running.";
  if (status >= 500) return "The server encountered an error. Please try again.";
  return "Request failed.";
}

async function parse(res) {
  let body = null;
  try {
    body = await res.json();
  } catch {
    /* non-JSON */
  }
  if (!res.ok) {
    const err = new ApiError(res.status, body?.detail || friendly(res.status));
    if (res.status === 401) onUnauthorized(err);
    throw err;
  }
  return body;
}

export async function request(path, { method = "GET", body, params, raw = false } = {}) {
  const url = new URL(BASE + path, window.location.origin);
  Object.entries(params || {}).forEach(([k, v]) => {
    if (v !== undefined && v !== null && v !== "") url.searchParams.set(k, v);
  });
  const headers = {};
  const token = getToken();
  if (token) headers.Authorization = `Bearer ${token}`;
  if (body !== undefined) headers["Content-Type"] = "application/json";
  let res;
  try {
    res = await fetch(url, { method, headers, body: body === undefined ? undefined : JSON.stringify(body) });
  } catch {
    throw new ApiError(0, friendly(0));
  }
  if (raw) {
    if (!res.ok) return parse(res);
    return res;
  }
  return parse(res);
}

export const api = {
  get: (path, params) => request(path, { params }),
  post: (path, body) => request(path, { method: "POST", body: body ?? {} }),
  patch: (path, body) => request(path, { method: "PATCH", body }),
  del: (path, params) => request(path, { method: "DELETE", params }),
};

/** Multipart upload with real progress events (XMLHttpRequest). */
export function uploadDocument(formData, onProgress) {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("POST", `${BASE}/documents/upload`);
    const token = getToken();
    if (token) xhr.setRequestHeader("Authorization", `Bearer ${token}`);
    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable) onProgress?.(Math.round((e.loaded / e.total) * 100));
    };
    xhr.onload = () => {
      let body = null;
      try {
        body = JSON.parse(xhr.responseText);
      } catch {
        /* ignore */
      }
      if (xhr.status >= 200 && xhr.status < 300) resolve(body);
      else {
        const err = new ApiError(xhr.status, body?.detail || friendly(xhr.status));
        if (xhr.status === 401) onUnauthorized(err);
        reject(err);
      }
    };
    xhr.onerror = () => reject(new ApiError(0, friendly(0)));
    xhr.send(formData);
  });
}

/** Fetch a stored file with auth and open it in a new tab. */
export async function openDocumentFile(documentId) {
  const win = window.open("", "_blank");
  try {
    const res = await request(`/documents/${documentId}/download`, { raw: true });
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    if (win) win.location.href = url;
    else window.location.assign(url);
    setTimeout(() => URL.revokeObjectURL(url), 60_000);
  } catch (e) {
    win?.close();
    throw e;
  }
}
