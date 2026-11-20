"""Is an uploaded file a medical document? Used for PATIENT uploads only (doctors and admins are trusted).

1. The type checks in document_processing.validate_upload run first (PDF / PNG / JPEG, real file signature, size).
2. Text: a PDF's own text, or, for photos and scanned PDFs, the text read by the LOCAL MedGemma 1.5 model on this
   computer (Ollama; the file never leaves the machine). The model is only asked to READ the text. It does not decide,
   because in testing it called a train ticket "medical" when asked directly. Its reading is used for this check only
   and is never stored as the document's text (a small model can misread numbers).
3. Rules decide, and say why: medical signs (test names, lab units, Rx, diagnosis, doctor/hospital headers...) against
   clear non-medical signs (CV, bank statement, ticket, restaurant bill...).

Results: MEDICAL (accepted), NOT_MEDICAL (rejected with the reason), UNSURE (accepted, marked "not checked" so the
doctor sees it: e.g. an X-ray image with no text, a blurry photo, or the local model not running).
"""

import base64
import re
from dataclasses import dataclass, field

import fitz
import httpx

from app.modules.ai.llm import strip_thinking
from app.core.config import get_settings

MEDICAL_TERMS = [
    r"ha?emoglobin|\bhb\b", r"platelet", r"\bwbc\b|white blood cell|leucocyte|leukocyte", r"\brbc\b|red blood cell",
    r"cholesterol|\bldl\b|\bhdl\b|triglyceride", r"hba1c|glycated", r"glucose|blood sugar", r"creatinine|\burea\b|\bbun\b",
    r"bilirubin|sgpt|sgot|\balt\b|\bast\b|alkaline phosphatase", r"\btsh\b|thyroid|\bt3\b|\bt4\b", r"\besr\b|\bcrp\b",
    r"urine|stool", r"x-?ray|radiograph|\bmri\b|\bct\b scan|ct scan|ultrasound|sonography|usg|mammogra", r"\becg\b|\bekg\b|echocardiog",
    r"biopsy|histopatholog|cytolog", r"impression|findings", r"diagnos[ie]s|provisional diagnosis", r"prescription|\brx\b",
    r"\btab\.?\b|tablet|capsule|\bcap\.?\b|syrup|\bsyp\b|injection|\binj\.?\b|ointment", r"\b(od|bd|tds|qid|sos|hs)\b|\d-\d-\d",
    r"discharge summary|admission|admitted|ward|\bopd\b|\bipd\b", r"patholog|radiolog|laborator|diagnostic", r"reference (range|interval|\d)|biological reference|normal range|\(ref",
    r"specimen|sample (collected|received|type)", r"patient(?:'s)? name|\bpatient\b|\buhid\b|\bmrn\b",
    r"\bage\s*/\s*sex\b|\bage\b.{0,12}\b(m|f|male|female)\b", r"\bdr\.?\s|\bmbbs\b|\bm\.?d\.?\b|consultant|physician|surgeon",
    r"hospital|clinic|medical cent(re|er)|health cent(re|er)", r"vaccin|immuni[sz]ation", r"\bdose\s*\d|\d+(st|nd|rd|th) dose|booster", r"blood pressure|\bbp\b|pulse|\bspo2\b",
    r"allerg", r"medical certificate|fit(ness)? certificate|sick leave", r"symptom|complain", r"follow[- ]?up|review after",
]
LAB_UNIT = re.compile(r"\b\d+(?:\.\d+)?\s*(?:mg/dl|g/dl|gm/dl|mmol/l|µmol/l|umol/l|u/l|iu/l|meq/l|ng/ml|ng/dl|pg/ml|µiu/ml|uiu/ml|miu/l|"
                      r"mm/hr|mm of hg|mmhg|cells/cumm|/cumm|/µl|/ul|x\s?10\^?\s?\d+\s?/\s?l|10\^\d+/l|lakhs?/cumm|fl\b|bpm)", re.I)
NON_MEDICAL_TERMS = [
    r"curriculum vitae|\bresume\b|work experience|\bskills\b", r"bank statement|account (no|number|statement)|\bifsc\b|closing balance|\bupi\b",
    r"salary|payslip|offer letter|appointment letter", r"\bpnr\b|e-?ticket|boarding pass|\bflight\b|railways?|\bcoach\b|\bberth\b",
    r"restaurant|\bmenu\b|table \d|\bdosa\b|\bpizza\b", r"semester|assignment|marksheet|\bgpa\b|university exam|question paper",
    r"lorem ipsum", r"invoice no|tax invoice|\bgstin\b", r"rent agreement|lease|electricity bill|mobile bill|recharge",
    r"aadhaar|\bpan card\b|passport|driving licen[cs]e|voter id",
]
_MED = [re.compile(p, re.I) for p in MEDICAL_TERMS]
_NON = [re.compile(p, re.I) for p in NON_MEDICAL_TERMS]
_MODEL_TOKENS = re.compile(r"<(?:start|end)_of_image>|<unused\d+>")
READ_PROMPT = "Transcribe all the text in this image exactly. If there is no text, describe the image in one sentence."
MIN_TEXT = 40  # fewer readable characters than this = nothing to judge


@dataclass
class Verdict:
    status: str  # MEDICAL / NOT_MEDICAL / UNSURE
    reason: str
    method: str  # "pdf text" / "text read by local MedGemma" / "none"
    medical_signs: list[str] = field(default_factory=list)
    other_signs: list[str] = field(default_factory=list)


def judge_text(text: str, method: str) -> Verdict:
    """Rules only. MEDICAL needs at least 3 medical signs, more than the non-medical ones; NOT_MEDICAL needs at most
    one medical sign and either a clear non-medical sign or plenty of text with no medical content at all."""
    text = (text or "").strip()
    if len(text) < MIN_TEXT:
        return Verdict("UNSURE", "Almost no readable text (for example an X-ray image or a blurry photo).", method)
    med = [m.group(0).strip() for p in _MED if (m := p.search(text))]
    units = LAB_UNIT.findall(text)
    if units:
        med.append(f"{len(units)} lab value(s) with units")
    non = [m.group(0).strip() for p in _NON if (m := p.search(text))]
    score = len(med) + min(len(units), 3)  # lab values with units are strong evidence
    if score >= 3 and score > 2 * len(non):
        return Verdict("MEDICAL", "Medical content found: " + ", ".join(med[:6]) + ".", method, med, non)
    if len(med) <= 1 and not units and (non or len(text) >= 300):  # a lab value with a unit is never rejected
        why = f"it looks like: {', '.join(x.lower() for x in non[:3])}" if non else "no medical content was found in its text"
        return Verdict("NOT_MEDICAL", f"This doesn't look like a medical document: {why}.", method, med, non)
    return Verdict("UNSURE", "Could not tell for certain whether this is a medical document.", method, med, non)


def _read_image(png_or_jpeg: bytes) -> str | None:
    """Text read by the local MedGemma model, or None if it is not available. Nothing is sent off this computer."""
    s = get_settings()
    if not s.medical_check_reader:
        return None
    try:
        r = httpx.post(f"{s.ollama_base_url.rstrip('/').removesuffix('/v1')}/api/chat", timeout=60, json={
            "model": s.medical_check_reader, "stream": False, "options": {"temperature": 0, "num_predict": 700},
            "messages": [{"role": "user", "content": READ_PROMPT, "images": [base64.b64encode(png_or_jpeg).decode()]}]})
        r.raise_for_status()
        return _MODEL_TOKENS.sub(" ", strip_thinking(r.json()["message"]["content"])).strip()
    except Exception:
        return None


def _first_page_png(pdf: bytes) -> bytes | None:
    try:
        doc = fitz.open(stream=pdf, filetype="pdf")
        return doc[0].get_pixmap(matrix=fitz.Matrix(1.5, 1.5)).tobytes("png")
    except Exception:
        return None


def check(data: bytes, extension: str, pdf_text: str | None) -> Verdict:
    if extension == ".pdf" and pdf_text and len(pdf_text.strip()) >= MIN_TEXT:
        return judge_text(pdf_text, "pdf text")
    image = _first_page_png(data) if extension == ".pdf" else data  # scanned PDF: read its first page
    text = _read_image(image) if image else None
    if text is None:
        return Verdict("UNSURE", "The local reading model is not running, so the content was not checked.", "none")
    return judge_text(text, "text read by local MedGemma")
