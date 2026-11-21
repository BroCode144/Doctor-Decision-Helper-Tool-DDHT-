"""Reading and checking a doctor's application documents. The model reads; rules decide; the admin approves.

Reader: a PDF's own text, or for photos / scanned PDFs the LOCAL Qwen2.5-VL model (Ollama, `DOCTOR_DOC_READER`).
The files never leave this computer. The model is only asked to write out the text it sees.

Rules then check, for each file: is it the right KIND of document (registration certificate, MBBS degree, photo ID,
postgraduate degree, hospital letter)? And for the application: does the registration number / name / council /
year on the documents match what the doctor typed? Is the registration number already used? Is a full (unmasked)
Aadhaar number visible?

This catches mistakes, wrong uploads and careless fakes. It cannot detect a well-made forgery: the admin still
searches the number on the NMC register, which is the real source of truth.
"""

import base64
import json
import re
import time
from dataclasses import dataclass

import fitz
import httpx
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import Doctor
from app.models.doctor_onboarding import ApplicationStatus, DoctorApplication
from app.modules.doctors import councils
KINDS = {
    "REGISTRATION": "Medical Council registration certificate",
    "DEGREE": "MBBS degree certificate",
    "PHOTO_ID": "Photo ID (masked Aadhaar, PAN or passport)",
    "PG_DEGREE": "Postgraduate degree (MD / MS / DNB)",
    "HOSPITAL_LETTER": "Hospital appointment letter or employee ID",
}
_SIGNS = {
    "REGISTRATION": [r"medical council|council of medical registration|medical commission|indian medical register",
                     r"registration|registered|reg\.?\s*no", r"medical practitioner|practi[sc]e|register"],
    "DEGREE": [r"universit|deemed to be", r"bachelor of medicine|m\.?\s?b\.?\s?b\.?\s?s|bachelor of surgery",
               r"degree|conferred|awarded|convocation|admitted to"],
    "PG_DEGREE": [r"doctor of medicine|master of surgery|\bm\.?\s?d\.?\b|\bm\.?\s?s\.?\b|\bd\.?\s?n\.?\s?b\b|diplomate of national board|post\s?-?graduate",
                  r"universit|national board", r"degree|diploma|conferred|awarded"],
    "PHOTO_ID": [r"aadhaa?r|unique identification authority|uidai", r"income tax department|permanent account number",
                 r"passport|republic of india", r"government of india", r"date of birth|\bdob\b|year of birth"],
    "HOSPITAL_LETTER": [r"hospital|medical cent(?:re|er)|clinic|nursing home|institute", r"appoint|employ|joining|designation|offer|this is to certify|staff|employee",
                        r"doctor|consultant|resident|physician|surgeon|medical officer|\bdr\.?\s"],
}
_ID_STRONG = re.compile(r"aadhaa?r|uidai|income tax department|permanent account number|passport", re.I)
_FULL_AADHAAR = re.compile(r"(?<!\d)\d{4}[ -]?\d{4}[ -]?\d{4}(?!\d)")
_YEAR = re.compile(r"\b(19[5-9]\d|20[0-4]\d)\b")
_MODEL_TOKENS = re.compile(r"<\|[^|>]*\|>|<(?:start|end)_of_image>")
MIN_TEXT = 40
READ_PROMPT = ("Write out all the text in this document exactly as printed, line by line. "
               "Do not explain, summarise or add anything.")


# ---------------------------------------------------------------------------
# Reading
# ---------------------------------------------------------------------------
def _pdf_text(data: bytes) -> str:
    try:
        doc = fitz.open(stream=data, filetype="pdf")
        return "\n".join(p.get_text() for p in doc)[:20000]
    except Exception:
        return ""


def _pdf_pages_png(data: bytes, pages: int = 2) -> list[bytes]:
    try:
        doc = fitz.open(stream=data, filetype="pdf")
        return [doc[i].get_pixmap(matrix=fitz.Matrix(2, 2)).tobytes("png") for i in range(min(pages, len(doc)))]
    except Exception:
        return []


GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
MAX_IMAGE_BYTES = 3_000_000  # Groq accepts up to 4 MB of base64 per image


def _shrink(img: bytes) -> tuple[bytes, str]:
    """Phone photos can be large: re-encode as JPEG and halve until it fits."""
    if len(img) <= MAX_IMAGE_BYTES:
        return img, "image/png" if img[:4] == b"\x89PNG" else "image/jpeg"
    pix = fitz.Pixmap(img)
    if pix.alpha:
        pix = fitz.Pixmap(pix, 0)
    out = pix.tobytes("jpeg", jpg_quality=85)
    while len(out) > MAX_IMAGE_BYTES and pix.width > 600:
        pix.shrink(1)
        out = pix.tobytes("jpeg", jpg_quality=85)
    return out, "image/jpeg"


def _read_image(img: bytes) -> str | None:
    """Text written out by the Groq vision model, or None if it is switched off / unreachable."""
    s = get_settings()
    if not (s.doctor_doc_reader and s.doctor_doc_groq_api_key):
        return None
    try:
        data, mime = _shrink(img)
        body = {"model": s.doctor_doc_reader, "temperature": 0, "max_tokens": 700,
                "messages": [{"role": "user", "content": [
                    {"type": "text", "text": READ_PROMPT},
                    {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{base64.b64encode(data).decode()}"}}]}]}
        for attempt in range(6):  # free tier: ~8,000 tokens a minute, so a 5-document application may have to wait
            r = httpx.post(GROQ_URL, timeout=60, headers={"Authorization": f"Bearer {s.doctor_doc_groq_api_key}"}, json=body)
            if r.status_code != 429 or attempt == 5:
                break
            time.sleep(min(float(r.headers.get("retry-after") or 15), 60))  # runs in the background job, not a request
        r.raise_for_status()
        return _MODEL_TOKENS.sub(" ", r.json()["choices"][0]["message"]["content"] or "").strip()
    except Exception:
        return None


READER_LABEL = "Groq AI (image)"
PRIVATE_KINDS = {"PHOTO_ID"}  # never sent to an outside service; the admin checks these by eye


def read(data: bytes, mime_type: str, kind: str | None = None) -> tuple[str | None, str]:
    """(text or None, how it was read). Text PDFs are read here; only scans/photos of certificates go to Groq."""
    if mime_type == "application/pdf":
        text = _pdf_text(data)
        if len(text.strip()) >= MIN_TEXT:
            return text, "pdf text"
        if kind in PRIVATE_KINDS:
            return None, "not read (ID kept private)"
        parts = [t for t in (_read_image(p) for p in _pdf_pages_png(data)) if t is not None]
        return ("\n".join(parts), READER_LABEL) if parts else (None, "not read")
    if kind in PRIVATE_KINDS:
        return None, "not read (ID kept private)"
    text = _read_image(data)
    return (text, READER_LABEL) if text is not None else (None, "not read")


# ---------------------------------------------------------------------------
# Rules
# ---------------------------------------------------------------------------
def _alnum(s: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", (s or "").upper())


def _name_tokens(name: str) -> list[str]:
    n = re.sub(r"\b(dr|doctor|mr|mrs|ms|prof)\b\.?", " ", (name or "").lower())
    return [t for t in re.findall(r"[a-z]+", n) if len(t) >= 2]


def name_match(name: str, text: str) -> str:
    """ok / partial / no. Initials and 'Dr.' are ignored; at least two-thirds of the name parts must appear."""
    tokens = _name_tokens(name)
    if not tokens:
        return "no"
    words = set(re.findall(r"[a-z]+", (text or "").lower()))
    hit = sum(1 for t in tokens if t in words)
    return "ok" if hit / len(tokens) >= 0.67 else "partial" if hit else "no"


def kind_signs(kind: str, text: str) -> list[str]:
    return [m.group(0).strip() for p in _SIGNS[kind] if (m := re.search(p, text, re.I))]


def looks_like(kind: str, text: str) -> bool:
    signs = kind_signs(kind, text)
    if kind == "PHOTO_ID":
        return bool(_ID_STRONG.search(text)) or len(signs) >= 2
    return len(signs) >= 2


@dataclass
class Check:
    label: str
    result: str  # ok / warn / fail / unknown
    detail: str = ""

    def as_dict(self) -> dict:
        return {"label": self.label, "result": self.result, "detail": self.detail}


def check_document(app: DoctorApplication, kind: str, text: str | None, method: str) -> dict:
    """Checks for ONE file. `block` = the doctor must re-upload it (wrong document, or a full Aadhaar number)."""
    title = KINDS[kind]
    if text is None or len(text.strip()) < MIN_TEXT:
        why = ("photo IDs are not sent to the AI service, for privacy" if "private" in method
               else "the document reader is off or unreachable" if method == "not read" else "almost no readable text")
        return {"kind": kind, "read": method, "kind_ok": None, "block": None,
                "checks": [Check(f"{title}: could not be read", "unknown", f"Check it by eye ({why}).").as_dict()]}
    checks: list[Check] = []
    ok_kind = looks_like(kind, text)
    signs = kind_signs(kind, text)
    checks.append(Check("Is the right kind of document", "ok" if ok_kind else "fail",
                        ("Found: " + ", ".join(signs)) if signs else "None of the expected wording was found."))
    block = None if ok_kind else f"This file doesn't look like a {title.lower()}."
    nm = name_match(app.full_name, text)
    checks.append(Check("Name matches the application", {"ok": "ok", "partial": "warn", "no": "fail"}[nm],
                        f"Looking for '{app.full_name}'" + ("" if nm == "ok" else " (only part of the name found)" if nm == "partial" else " (not found)")))
    if kind == "REGISTRATION":
        reg = _alnum(app.registration_number)
        found = len(reg) >= 4 and reg in _alnum(text)
        checks.append(Check("Registration number matches", "ok" if found else "fail",
                            f"Looking for {app.registration_number}" + ("" if found else " (not on the certificate)")))
        words = councils.COUNCILS.get(app.council, ("", []))[1]
        council_ok = any(w in text.lower() for w in words)
        others = [councils.name(c) for c, (_, ws) in councils.COUNCILS.items() if c != app.council and any(w in text.lower() for w in ws)]
        checks.append(Check("Council matches", "ok" if council_ok else "fail",
                            councils.name(app.council) + ("" if council_ok else f" not found{'; the certificate mentions ' + others[0] if others else ''}")))
        year_ok = str(app.registration_year) in text
        checks.append(Check("Registration year matches", "ok" if year_ok else "warn",
                            f"Looking for {app.registration_year}" + ("" if year_ok else " (not found)")))
    if kind == "DEGREE":
        years = sorted({int(y) for y in _YEAR.findall(text)})
        if years and min(years) > app.registration_year:
            checks.append(Check("Degree before registration", "fail", f"Degree shows {min(years)}, registration year is {app.registration_year}."))
        elif years:
            checks.append(Check("Degree before registration", "ok", f"Degree year {min(years)}, registration {app.registration_year}."))
    if kind == "PHOTO_ID" and re.search(r"aadhaa?r|uidai", text, re.I) and _FULL_AADHAAR.search(text):
        checks.append(Check("Aadhaar is masked", "fail", "A full 12-digit Aadhaar number is visible. Only masked Aadhaar is accepted."))
        block = block or "A full Aadhaar number is visible; please upload a masked Aadhaar (first 8 digits hidden), PAN or passport."
    return {"kind": kind, "read": method, "kind_ok": ok_kind, "block": block, "checks": [c.as_dict() for c in checks]}


def application_checks(db: Session, app: DoctorApplication) -> list[dict]:
    """Checks that don't depend on a single file."""
    out: list[Check] = []
    reg = _alnum(app.registration_number)
    dup_doc = db.scalar(select(Doctor.id).where(func.upper(func.regexp_replace(Doctor.license_number, "[^A-Za-z0-9]", "", "g")) == reg))
    dup_app = db.scalar(select(DoctorApplication.id).where(
        DoctorApplication.id != app.id, DoctorApplication.status != ApplicationStatus.REJECTED,
        func.upper(func.regexp_replace(DoctorApplication.registration_number, "[^A-Za-z0-9]", "", "g")) == reg,
        DoctorApplication.council == app.council))
    if dup_doc or dup_app:
        out.append(Check("Registration number not already used", "fail",
                         f"Already used by {'doctor ' + dup_doc if dup_doc else 'application ' + dup_app}."))
    else:
        out.append(Check("Registration number not already used", "ok"))
    current = {d.kind for d in app.documents if not d.superseded}
    need = ["REGISTRATION", "DEGREE", "PHOTO_ID"] + (["PG_DEGREE"] if app.claims_specialist else [])
    missing = [KINDS[k] for k in need if k not in current]
    out.append(Check("All required documents uploaded", "fail" if missing else "ok", ("Missing: " + ", ".join(missing)) if missing else ""))
    if app.hospital_id and "HOSPITAL_LETTER" not in current:
        out.append(Check("Hospital link supported", "warn", "A hospital was chosen but no appointment letter / employee ID was uploaded."))
    return [c.as_dict() for c in out]


def summary(db: Session, app: DoctorApplication) -> dict:
    docs = [json.loads(d.check_result) for d in app.documents if not d.superseded and d.check_result]
    overall = application_checks(db, app)
    every = overall + [c for d in docs for c in d["checks"]]
    return {"overall": overall, "documents": docs,
            "counts": {r: sum(1 for c in every if c["result"] == r) for r in ("ok", "warn", "fail", "unknown")},
            "blocks": [{"kind": d["kind"], "title": KINDS[d["kind"]], "reason": d["block"]} for d in docs if d.get("block")]}
