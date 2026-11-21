"""Intake chat engine: a natural conversation that silently fills the intake schema (app.modules.booking.intake_schema).

The patient sees only the chat. Every turn:
1. Fixed word rules read the message (symptoms, "since 3 days", "fever of 102", "BP 140/90 on my Omron", warning
   signs, trips). They work without any AI.
2. This module decides what matters next, in a fixed priority: the main problem; warning signs that fit THIS
   problem (asked one at a time, never a checklist); the device behind any home reading; when it started and how it
   is going; the fields of the active symptom groups; family history when hereditary or metabolic problems overlap;
   then (new patients) the baseline. At most MAX_QUESTIONS questions after the main problem (warning signs are always
   asked); consent is a checkbox on the booking page, not a chat question.
3. The AI (intake-only system prompt) words the next question and pulls values out of the message. It may also
   choose a short "probe": an unmentioned symptom that would help tell possible causes apart. It reasons about
   causes privately; nothing about causes ever reaches the patient: its message must pass guard(), which rejects
   disease names (except when asking about family or known conditions), cause/likelihood language and checklists.
   Every value it fills must quote the patient's own words (evidenced()); hedged or unquoted values are dropped.
   If the AI fails, a fixed natural question is used.
A warning sign the patient states about themselves stops the routine questions at once (urgent-care banner; the
doctor is alerted when the booking is sent). One mentioned about someone else, or in the past, is checked first.
Home readings are stored as {value, unit, source_device, reliability_score, reliability_tier} (score_device()).
Nothing is saved until the booking is sent, and only with consent_processing = yes.
"""

import json
import logging
import re
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.ai.llm import LLMUnavailableError
from app.core.errors import AppError
from app.models import Document, HealthHistoryItem, IntakeRecord, Patient, PatientBaseline, Prescription, User
from app.modules.booking import cities
from app.modules.records import history
from app.modules.booking import questionnaire
from app.modules.appointments.service import now_utc
from app.modules.booking.intake_schema import (BASELINE_PRIORITY, BY_ID, CLUSTER_RED_FLAGS, CLUSTER_TRIGGERS, CLUSTERS, CODES,
                                        FIELDS, HEREDITARY_CLUSTERS, RED_FLAG_FIELDS, SECTIONS, SYMPTOM_TOGGLES,
                                        VITALS)

log = logging.getLogger(__name__)

MAX_MESSAGES = 20  # conversation kept in the state (and sent to the AI)
MAX_PROBES = 5  # unmentioned-symptom questions the AI may add per conversation
MAX_QUESTIONS = 6  # detail questions after the main problem; the booking page asks the rest with one-tap buttons
# Always asked even after MAX_QUESTIONS (only when they apply): what a doctor must know before prescribing.
ESSENTIAL = ["drug_allergies", "current_medicines", "chronic_conditions", "records_medicines_still_taking",
             "records_conditions_changed", "parental_and_family_history", "family_history_changed"]
DEVICE = "device:"  # target prefix: "which device measured this reading?"

# ---------------------------------------------------------------------------
# Home readings: device -> reliability (fixed rubric, so the diagnostic model can weight the value)
# ---------------------------------------------------------------------------
TIERS = {"high": "High (medical-grade instrument)", "moderate_high": "Moderate-high (validated wearable)",
         "low": "Low (budget band, or a wrist-based estimate)", "unverified": "Unverified (device not known)"}
_UNKNOWN_DEVICE = re.compile(r"don'?t (know|remember)|not sure|no idea|forgot|can'?t remember|pata nahi|^\s*(no|none)\s*$", re.I)
_VALIDATED_WEARABLE = re.compile(r"apple ?watch|whoop|garmin|galaxy ?watch|samsung (galaxy )?watch|fitbit|oura|pixel ?watch|withings", re.I)
_BUDGET = re.compile(r"smart ?watch|fitness ?band|\bband\b|tracker|\bnoise\b|\bboat\b|fire-?boltt|mi ?band|amazfit|\blocal\b|cheap|₹|\brs\.? ?\d", re.I)
_MEDICAL = re.compile(r"cuff|upper.?arm|bp (machine|monitor|apparatus)|sphygmo|omron|morepen|beurer|rossmax|accusure|pulse ?ox|oximeter|"
                      r"thermometer|mercury|glucometer|gluco ?meter|accu-?chek|one ?touch|contour|freestyle|libre|clinic|hospital|"
                      r"pharmacy|chemist|doctor|nurse|\blab\b", re.I)
_NON_CONTACT = re.compile(r"forehead|infra-?red|\bir\b|non-?contact|gun", re.I)


def score_device(vital: str, device: str | None) -> tuple[float, str]:
    """(reliability_score, tier) for a reading taken with `device`, by the rubric:
    medical-grade 0.85-1.0, validated wearable 0.70-0.84, budget band or wrist-based BP estimate 0.20-0.45,
    unknown device 0.10. A watch or wrist cuff measuring blood pressure is a wrist-based estimate (low)."""
    d = (device or "").strip()
    if not d or _UNKNOWN_DEVICE.search(d):
        return 0.10, "unverified"
    watch = bool(_VALIDATED_WEARABLE.search(d) or _BUDGET.search(d) or re.search(r"watch", d, re.I))
    if vital == "home_bp" and (watch or (re.search(r"wrist", d, re.I) and not re.search(r"upper.?arm", d, re.I))):
        return 0.40, "low"
    if vital in ("highest_temp", "home_temp") and watch:
        return 0.30, "low"  # skin temperature from a wrist device
    if _VALIDATED_WEARABLE.search(d):
        return 0.78, "moderate_high"
    if _BUDGET.search(d):
        return 0.30, "low"
    if _MEDICAL.search(d):
        return (0.85 if vital in ("highest_temp", "home_temp") and _NON_CONTACT.search(d) else 0.92), "high"
    return 0.10, "unverified"


def _vital(fid: str, v, old: dict | None = None) -> dict | None:
    """A home reading as {value, unit, source_device, reliability_score, reliability_tier}, or None if invalid.
    Accepts a number, "130/85", or {"value", "unit", "source_device"}; merges with what was already known."""
    spec = VITALS[fid]
    out = dict(old or {})
    raw = v if isinstance(v, dict) else {"value": v}
    if raw.get("value") not in (None, ""):
        val, unit = raw["value"], raw.get("unit")
        if "pattern" in spec:
            val = re.sub(r"\s", "", str(val))
            if not re.match(spec["pattern"], val):
                return None
            unit = spec["units"][0]
        else:
            try:
                val = float(re.sub(r"[^\d.]", "", str(val)) or "x")
            except ValueError:
                return None
            if unit not in spec["units"]:
                unit = ("°F" if val > 45 else "°C") if fid in ("highest_temp", "home_temp") else spec["units"][0]
            lo, hi = spec["range"][unit]
            if not lo <= val <= hi:
                return None
            val = int(val) if val == int(val) else round(val, 1)
        out.update(value=val, unit=unit)
    if "value" not in out:
        return None
    if isinstance(raw.get("source_device"), str) and raw["source_device"].strip():
        out["source_device"] = " ".join(raw["source_device"].split())[:80]
    if out.get("source_device"):
        score, tier = score_device(fid, out["source_device"])
        out.update(reliability_score=score, reliability_tier=tier)
    else:
        out.update(source_device=None, reliability_score=None, reliability_tier="device_not_asked_yet")
    return out


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------
_TIME = re.compile(r"^([01]?\d|2[0-3]):[0-5]\d$")


def _valid(f: dict, v, old=None):
    """The value cleaned for field f, or None if it isn't valid (invalid values are dropped, never guessed)."""
    if v is None or v == "":
        return None
    k = f["kind"]
    try:
        if k == "vital":
            return _vital(f["id"], v, old if isinstance(old, dict) else None)
        if k == "bool":
            return v if isinstance(v, bool) else None
        if k == "enum":
            return v if v in {o["value"] for o in f["options"]} else None
        if k == "multi":
            ok = {o["value"] for o in f["options"]}
            vals = [x for x in dict.fromkeys(v if isinstance(v, list) else [v]) if x in ok]
            return (["none"] if "none" in vals else vals) or None
        if k in ("int", "num"):
            n = float(v)
            if k == "int":
                n = int(round(n))
            if ("min" in f and n < f["min"]) or ("max" in f and n > f["max"]):
                return None
            return n
        if k == "date":
            d = date.fromisoformat(str(v)[:10])
            return d.isoformat() if date(1900, 1, 1) <= d <= date.today() else None
        if k == "time":
            return str(v) if _TIME.match(str(v)) else None
        if k == "text":
            t = " ".join(str(v).split())[: f.get("max", 300)]
            return t or None
        if k == "tags":
            names = [" ".join(str(x).split())[:100] for x in (v if isinstance(v, list) else str(v).split(","))]
            return list(dict.fromkeys(n for n in names if len(n) >= 2))[: f.get("max_items", 15)] or None
        if k == "list":
            rows = []
            for r in (v if isinstance(v, list) else [v])[:20]:
                if isinstance(r, dict):
                    row = {i["id"]: " ".join(str(r.get(i["id"]) or "").split())[: i.get("max", 100)] for i in f["item_fields"]}
                    if any(row.values()):
                        rows.append(row)
            return rows or None
    except (TypeError, ValueError):
        return None
    return None


def clean_form(raw) -> dict:
    """Only known, editable fields with valid values; computed fields are recalculated."""
    raw = raw if isinstance(raw, dict) else {}
    out = {}
    for f in FIELDS:
        if f.get("computed"):
            continue
        v = _valid(f, raw.get(f["id"]))
        if v is not None:
            out[f["id"]] = v
    return compute(out)


def compute(form: dict) -> dict:
    for k in ("age", "bmi", "duration_days", "pack_years"):
        form.pop(k, None)
    for f in FIELDS:  # a follow-up whose question no longer applies (e.g. "where" after "travelled: no") is dropped
        for k, want in (f.get("only_if") or {}).items():
            if f["id"] in form and ((form.get(k) not in want) if isinstance(want, list) else (form.get(k) != want)):
                form.pop(f["id"])
    today = date.today()
    if form.get("dob"):
        d = date.fromisoformat(form["dob"])
        form["age"] = today.year - d.year - ((today.month, today.day) < (d.month, d.day))
    if form.get("height_cm") and form.get("weight_kg"):
        form["bmi"] = round(form["weight_kg"] / (form["height_cm"] / 100) ** 2, 1)
    if form.get("onset_date"):
        form["duration_days"] = (today - date.fromisoformat(form["onset_date"])).days
    if form.get("cigarettes_per_day") is not None and form.get("smoking_years") is not None:
        form["pack_years"] = round(form["cigarettes_per_day"] / 20 * form["smoking_years"], 1)
    return form


def applies(f: dict, form: dict, ctx: dict) -> bool:
    if f.get("computed") or f.get("readonly"):
        return False
    if f.get("only_female") and form.get("gender") != "female":
        return False
    if f.get("existing_only"):
        need = {"records_conditions_changed": "conditions", "records_medicines_still_taking": "medicines",
                "family_history_changed": "family"}[f["id"]]
        if not ctx.get(need):
            return False
    for k, want in (f.get("only_if") or {}).items():
        have = form.get(k)
        if (have not in want) if isinstance(want, list) else (have != want):
            return False
    return True


# ---------------------------------------------------------------------------
# What the records already say (existing patients)
# ---------------------------------------------------------------------------
_CONDITION_WORDS = [("diabetes", r"diabet"), ("hypertension", r"hypertens|blood pressure"), ("asthma", r"asthma"),
                    ("copd", r"copd|chronic obstructive"), ("thyroid", r"thyroid"), ("kidney", r"kidney|renal"),
                    ("liver", r"liver|hepat"), ("heart", r"heart|cardiac|coronary"), ("epilepsy", r"epilep")]
_LAB_KEYS = {"hemoglobin": "Haemoglobin", "platelets": "Platelets", "wbc": "White cell count", "creatinine": "Creatinine",
             "alt": "ALT (liver enzyme)", "ast": "AST (liver enzyme)", "fasting_glucose": "Fasting blood sugar",
             "hba1c": "HbA1c", "tsh": "TSH (thyroid)"}
# Reads lab values out of a report's text: (text, document) -> [(key, value, unit, date or None)]. Registered by the
# optional lab-reading module when it is installed; without it, intake simply has no lab baselines.
LAB_READER = None


def hydrate(db: Session, patient: Patient) -> tuple[dict, dict]:
    """(form pre-filled from the database, context). Pre-filled fields are listed in context["from_records"]."""
    form: dict = {}
    base = db.get(PatientBaseline, patient.id)
    if base:
        form.update({k: v for k, v in base.data.items() if k in BY_ID})
    g = (patient.gender or "").strip().lower()
    if g in ("male", "m", "female", "f"):
        form["gender"] = "male" if g.startswith("m") else "female"
    if patient.date_of_birth:
        form["dob"] = patient.date_of_birth.isoformat()
    items = db.scalars(select(HealthHistoryItem).where(HealthHistoryItem.patient_id == patient.id,
                                                       HealthHistoryItem.removed_at.is_(None))).all()
    allergies = [i.name for i in items if i.kind == "ALLERGY"]
    if allergies:
        form["drug_allergies"] = allergies
    elif any(i.kind == history.NKA for i in items):
        form["no_known_allergies"] = True
    conditions = [i.name for i in items if i.kind == "CONDITION"]
    cond_codes = [code for code, pat in _CONDITION_WORDS if any(re.search(pat, c, re.I) for c in conditions)]
    if conditions:
        form["chronic_conditions"] = cond_codes + (["others"] if len(cond_codes) < len(conditions) else [])
    rx = db.scalars(select(Prescription).where(Prescription.patient_id == patient.id, Prescription.status == "Active")
                    .order_by(Prescription.prescribed_date.desc()).limit(10)).all()
    meds = [{"drug_name": r.medication, "dose": r.dosage or "", "frequency": "", "reason": "prescribed"} for r in rx]
    meds += [{"drug_name": i.name, "dose": "", "frequency": "", "reason": i.detail or ""} for i in items if i.kind == "MEDICATION"]
    if meds:
        form["current_medicines"] = meds
    if surg := [{"type": i.name, "year": (i.detail or "")[:4]} for i in items if i.kind == "SURGERY"]:
        form["prior_surgeries"] = surg
    family = [{"relation": i.detail or "", "condition": i.name, "age_at_onset": ""} for i in items if i.kind == "FAMILY"]
    if family:
        form["parental_and_family_history"] = family
    prev = questionnaire.latest(db, patient.id)
    if prev:
        form.setdefault("smoking", {"now": "current", "former": "former", "never": "never"}.get(prev.smoking))
        if prev.city and prev.city != cities.OTHER:
            form.setdefault("location", prev.city)
        if prev.diabetes == "yes" and "diabetes" not in form.get("chronic_conditions", []):
            form["chronic_conditions"] = [c for c in form.get("chronic_conditions", []) if c != "none"] + ["diabetes"]
    labs = _latest_labs(db, patient.id)
    form = clean_form({k: v for k, v in form.items() if v is not None})
    if labs:
        form["last_known_labs"] = labs
    ctx = {"returning": bool(items or rx or prev or base), "name": patient.full_name.split()[0],
           "conditions": conditions, "medicines": [m["drug_name"] for m in meds],
           "family": [f"{x['condition']} ({x['relation']})" if x["relation"] else x["condition"] for x in family],
           "allergies": allergies, "from_records": sorted(k for k in form if not BY_ID.get(k, {}).get("computed")),
           "last_booking": prev.created_at.date().isoformat() if prev else None}
    return form, ctx


def _latest_labs(db: Session, patient_id: str) -> list[dict]:
    if LAB_READER is None:
        return []
    docs = db.scalars(select(Document).where(Document.patient_id == patient_id, Document.extracted_text.is_not(None))).all()
    latest: dict[str, tuple] = {}
    for d in docs:
        try:
            found = LAB_READER(d.extracted_text, d)
        except Exception:  # a report that can't be read is skipped
            continue
        for key, value, unit, when in found:
            if key in _LAB_KEYS and (key not in latest or (when or date.min) >= (latest[key][2] or date.min)):
                latest[key] = (value, unit, when)
    return [{"test": label, "value": f"{latest[k][0]:g} {latest[k][1]}".strip(),
             "date": latest[k][2].isoformat() if latest[k][2] else ""} for k, label in _LAB_KEYS.items() if k in latest]


# ---------------------------------------------------------------------------
# Fixed word rules (work without AI)
# ---------------------------------------------------------------------------
TOGGLE_WORDS = {
    "fever_present": r"fever|bu?kh?aa?r|feverish|high temperature",
    "headache": r"head ?ache|sir ?dard|migraine|head (is )?(pain|hurt)",
    "cough": r"cough|kh[aā]a?n?si",
    "sore_throat": r"sore throat|throat (pain|is sore|hurts)|gala dard",
    "runny_nose": r"runny nose|\bcold\b|sneez|z[uo]ka?m|jukam|blocked nose",
    "shortness_of_breath": r"breathless|short of breath|breathing (difficulty|problem|trouble)|saa?ns",
    "chest_discomfort": r"chest (pain|tight|pressure|discomfort|heav)",
    "abdominal_pain": r"stomach ?(pain|ache)|abdominal pain|belly pain|tummy (pain|ache)|pet ?(me[in]* )?dard",
    "heartburn": r"heartburn|acidity|sour (taste|burp)|acid reflux",
    "nausea_vomiting": r"vomit|nause|\bult[iy]|throwing up",
    "diarrhea": r"diarr?h|loose (motion|stool)|\bdast",
    "constipation": r"constipat|hard stool|kabz",
    "itching": r"itch|kh[uo]jli",
    "skin_rash": r"rash|red spots|hives",
    "mouth_ulcers": r"mouth ulcer|ulcers? in (the |my )?mouth|chhal",
    "jaundice_eyes_skin": r"yellow (eyes|skin)|jaundice|piliya",
    "dark_urine": r"dark (yellow )?urine|cola.colou?red urine",
    "dysuria": r"burning (urine|urination|while peeing|when (i )?pee)|painful urination|peshab (me[in]* )?jalan",
    "bleeding_gums_bruising": r"bleeding gums|gums? bleed|nose ?bleed|bruis",
    "blood_in_stool_urine": r"blood in (the |my )?(stool|urine|motion)|bloody (stool|urine)",
    "muscle_aches": r"body ?(pain|ache)|muscle (pain|ache)|badan dard",
    "joint_pain": r"joint pain|joints? (hurt|ache|pain)|jodo[n]? (me[in]* )?dard",
    "chills": r"chills?|shiver|rigou?rs?|kaa?np",
    "sweating": r"sweat|paseena",
    "fatigue": r"tired|fatigue|exhaust|no energy|low energy|thakan",
    "weight_gain": r"(gained|gaining|put on) (some |a lot of )?weight|weight gain",
    "cold_intolerance": r"(feel|feeling) (very |always )?cold|cold all the time",
    "hair_skin_changes": r"hair (fall|loss|is falling)|dry skin",
    "neck_swelling": r"(swelling|lump) (in|on) (my |the )?neck|neck (swelling|lump)",
    "excessive_thirst": r"(very |always |too )thirsty|excessive thirst|drinking a lot of water",
    "palpitations": r"palpitation|heart (is )?(racing|pounding)|dhadkan",
    "night_sweats": r"night sweats|sweat(ing)? at night",
    "leg_swelling": r"(swollen|swelling (in|of)) (my )?(feet|legs|ankles)",
    "numbness_tingling": r"\bnumb(ness)?\b|tingl|pins and needles|jhunjhuni",
    "vision_changes": r"blurr(ed|y) vision|vision (is )?(blurr|changed)|can'?t see (clearly|properly)",
}
RED_FLAG_WORDS = {
    "chest_pain": r"chest (pain|pressure|tight)|seen[ea] (me[in]* )?dard",
    "severe_breathlessness": r"can'?t breathe|cannot breathe|severe(ly)? breathless|gasping|struggling to breathe|breathless (at|while) rest",
    "confusion_fainting": r"faint|passed out|confus|very drowsy|unconscious|behosh",
    "uncontrolled_bleeding": r"vomit(ing|ed)? blood|blood in (my |the )?vomit|bleeding (won'?t|will not|doesn'?t) stop|heavy bleeding",
    "fluid_intolerance_low_urine": r"can'?t keep (water|fluids|anything) down|not passing urine|very little urine|no urine",
    "seizure_or_stiff_neck": r"seizure|\bfits?\b|convulsion|stiff neck|neck (is )?stiff",
}
_OTHER_PERSON = re.compile(r"\b(father|mother|dad|mom|mum|papa|mummy|brother|sister|son|daughter|wife|husband|grand\w*|"
                           r"uncle|aunt|friend|relative|cousin|neighbou?r|parents?)\b", re.I)
_PAST = re.compile(r"\b(last (year|month)|years? ago|months ago|in the past|used to|long ago|earlier this year|as a child)\b", re.I)
_NEG = re.compile(r"\b(no|not|without|nahi|nahin|never|don'?t have|denies)\b", re.I)
_NUM = {"a": 1, "an": 1, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "ten": 10}
_DUR = re.compile(r"\b(\d{1,3}|a|an|one|two|three|four|five|six|seven|ten)\s*(day|din|week|hafta|month|mahin)", re.I)
_TEMP = re.compile(r"\b(\d{2,3}(?:\.\d)?)\s*(?:°|deg(?:rees?)?)?\s*([fc])?\b", re.I)
_TIMEISH = re.compile(r"\b(day|days|week|weeks|month|months|year|ago|since|while|long|recent|recently|morning|night|"
                     r"yesterday|today|kal|din|hafta|mahin|not sure|don'?t (know|remember)|few|couple|some time)\b", re.I)
_RELATIVE = r"(mother|father|mom|mum|dad|papa|mummy|brother|sister|grand(?:mother|father|ma|pa)|parents?|uncle|aunt)"
_FAMILY_CONDITIONS = [("Thyroid problem", r"thyroid"), ("Diabetes", r"diabet|sugar"), ("High blood pressure", r"\bbp\b|blood pressure|hypertension"),
                      ("Heart disease", r"heart"), ("Stroke", r"stroke|paralysis"), ("Cancer", r"cancer"),
                      ("Liver disease", r"liver"), ("Kidney disease", r"kidney"), ("Tuberculosis", r"\btb\b|tuberculosis"),
                      ("Thalassemia or sickle cell", r"thalass|sickle"), ("Asthma", r"asthma")]


def family_rows(text: str) -> list[dict]:
    """'my mother has thyroid and my father has high BP' -> [{relation: mother, condition: Thyroid problem}, ...]."""
    rows = []
    for part in re.split(r"[.;]|,?\s*\band\s+(?=(?:my|his|her|our|both)\b)|,\s*(?=my\b)", text, flags=re.I):
        rel = re.search(_RELATIVE, part, re.I)
        if not rel or _negated(part[:rel.start()]):
            continue
        for name, pat in _FAMILY_CONDITIONS:
            hit = re.search(pat, part, re.I)
            if hit and not _negated(part[:hit.start()]):
                rows.append({"relation": rel.group(1).lower(), "condition": name, "age_at_onset": ""})
    return rows


_VITAL_WORDS = {
    "home_bp": re.compile(r"\b(?:bp|blood pressure|pressure)\b[^\d]{0,20}(\d{2,3}\s*/\s*\d{2,3})", re.I),
    "home_spo2": re.compile(r"\b(?:spo2|sp ?o2|oxygen|saturation|o2)\b[^\d]{0,20}(\d{2,3})", re.I),
    "home_hr": re.compile(r"\b(?:pulse|heart ?rate|hr|heartbeat)\b[^\d]{0,20}(\d{2,3})", re.I),
    "home_glucose": re.compile(r"\b(?:sugar|glucose)\b[^\d]{0,20}(\d{2,3})", re.I),
}
_DEVICE_WORDS = re.compile(r"\b(?:on|with|using|by|from) (?:my |a |the |an )?([\w\- ]{0,30}?(?:watch|band|machine|monitor|meter|"
                           r"oximeter|thermometer|cuff|tracker|omron|morepen|fitbit|garmin|whoop|libre|accu-?chek))", re.I)


def _sentence(text: str, pos: int) -> str:
    start = max(text.rfind(c, 0, pos) for c in ".!?;\n") + 1
    ends = [i for i in (text.find(c, pos) for c in ".!?;\n") if i != -1]
    return text[start:min(ends) if ends else len(text)]


def _negated(before: str) -> bool:
    """'no cough' is negated; in 'no cough, and chest pain' the chest pain is not (a comma, 'and', 'but' ends it)."""
    last = None
    for last in _NEG.finditer(before):
        pass
    if last is None:
        return False
    gap = before[last.end():]
    return len(gap) <= 15 and not re.search(r"[,.;]|\b(and|but|aur|lekin)\b", gap, re.I)


def _about_others(text: str, pos: int) -> bool:
    """Said about someone else ("my father had...") or about the past ("last year"), not the patient now."""
    s = _sentence(text, pos)
    return bool(_OTHER_PERSON.search(s) or _PAST.search(s))


def _said(pattern: str, text: str) -> bool:
    return any(not _negated(text[:m.start()]) for m in re.finditer(pattern, text, re.I))


def _denied(pattern: str, text: str) -> bool:
    return any(_negated(text[:m.start()]) for m in re.finditer(pattern, text, re.I))


def rule_patch(text: str) -> tuple[dict, list[str], list[str]]:
    """(values stated in the text, warning signs the patient states about themselves now, warning signs to check
    first because they were said about someone else or about the past)."""
    patch: dict = {}
    full = text
    for fid, pat in TOGGLE_WORDS.items():
        hits = [h for h in re.finditer(pat, full, re.I) if not _about_others(full, h.start())]
        if any(not _negated(full[:h.start()]) for h in hits):
            patch[fid] = True
        elif any(_negated(full[:h.start()]) for h in hits):
            patch[fid] = False
    trip = re.search(r"\b(?:came back|returned|back|travel+ed|trip|went|visited|been)\b[\w ]{0,20}?\b(?:from|to|in)\s+"
                     r"([A-Z][a-zA-Z]+(?: [A-Z][a-zA-Z]+)?)", text)
    if trip and not _negated(text[:trip.start()]):
        ago = re.search(r"(\d{1,3}|a|one|two|three|four|five|six|seven|ten)\s*(day|week|month)s?\s*ago", text[trip.start():], re.I)
        days = None
        if ago:
            n = int(ago.group(1)) if ago.group(1).isdigit() else _NUM.get(ago.group(1).lower(), 1)
            days = n * {"day": 1, "week": 7, "month": 30}[ago.group(2).lower()]
        if days is not None and days <= 3:
            patch["travel_3d"], patch["travel_3d_destination"] = True, trip.group(1)
        if days is None or days <= 90:
            patch["travel_30d_3m"], patch["travel_30d_3m_destination"] = True, trip.group(1)
        text = text[:trip.start()] + " " + text[trip.start() + (ago.end() if ago else trip.end() - trip.start()):]
    m = _DUR.search(text)
    days = None
    if m:
        n = int(m.group(1)) if m.group(1).isdigit() else _NUM[m.group(1).lower()]
        unit = m.group(2).lower()
        days = n * (7 if unit in ("week", "hafta") else 30 if unit in ("month", "mahin") else 1)
    elif re.search(r"\b(since |from )?(yesterday|last night|kal se)\b", text, re.I):
        days = 1
    elif re.search(r"\b(today|this morning|since morning|aaj)\b", text, re.I):
        days = 0
    if days is not None and days <= 3650:
        patch["onset_date"] = (date.today() - timedelta(days=days)).isoformat()
    if re.search(r"fever|temp|bukhar", text, re.I):
        for t in _TEMP.finditer(text):
            val, unit = float(t.group(1)), (t.group(2) or "").upper()
            unit = {"F": "°F", "C": "°C"}.get(unit) or ("°F" if 93 <= val <= 110 else "°C" if 34 <= val <= 43.5 else "")
            if unit:
                patch["highest_temp"] = {"value": val, "unit": unit}
                break
    for fid, pat in _VITAL_WORDS.items():
        if (vm := pat.search(full)):
            patch[fid] = {"value": vm.group(1)}
    if (fam := family_rows(full)):
        patch["parental_and_family_history"] = fam
    if (device := _DEVICE_WORDS.search(full)):
        for fid in VITALS:
            if isinstance(patch.get(fid), dict):
                patch[fid]["source_device"] = device.group(1).strip()
    if re.search(r"getting worse|worse(ning)?\b|getting stronger|more and more", text, re.I) and not re.search(r"worse (at|in|when|after)", text, re.I):
        patch["trend"] = "worse"
    elif re.search(r"getting better|improving|less than before", text, re.I):
        patch["trend"] = "getting_better"
    now, check = [], []
    for fid, pat in RED_FLAG_WORDS.items():
        for hit in re.finditer(pat, full, re.I):
            if _negated(full[:hit.start()]):
                continue
            (check if _about_others(full, hit.start()) else now).append(fid)
            break
    return patch, list(dict.fromkeys(now)), [c for c in dict.fromkeys(check) if c not in now]


# ---------------------------------------------------------------------------
# What to ask next (fixed priorities)
# ---------------------------------------------------------------------------
def active_clusters(form: dict) -> list[str]:
    return [c for c, triggers in CLUSTER_TRIGGERS.items() if any(form.get(t) is True for t in triggers)]


def _asked(asked: dict, fid: str) -> bool:
    return asked.get(fid, 0) >= 1


def missing_fields(form: dict, ctx: dict, asked: dict) -> list[str]:
    """What to ask, best first (field ids, or "device:<reading>"). A question asked once and still unanswered (the
    patient didn't know) isn't asked again."""
    clusters = active_clusters(form)
    order: list[str] = ["main_symptoms_narrative"]
    for c in clusters:
        order += CLUSTER_RED_FLAGS.get(c, [])
    devices = [f"{DEVICE}{fid}" for fid in VITALS if isinstance(form.get(fid), dict) and not form[fid].get("source_device")
               and not _asked(asked, f"{DEVICE}{fid}")]
    order += ["onset_date", "trend"]
    if form.get("gender") == "female" and (form.get("age") is None or 12 <= form["age"] <= 55):
        order.append("pregnancy_possible")
    if any(form.get(t) for t in ("muscle_aches", "joint_pain", "headache", "abdominal_pain", "chest_discomfort")):
        order.append("pain_severity_0_10")
    for c in clusters:
        order += CLUSTERS[c]
    if set(clusters) & HEREDITARY_CLUSTERS:
        order.append("family_history_changed" if ctx.get("family") else "parental_and_family_history")
    if ctx.get("returning"):
        order += ["records_medicines_still_taking", "records_conditions_changed"]
    order += BASELINE_PRIORITY
    if form.get("onset_date") and "fever_present" not in form:
        order.append("fever_present")
    out = []
    for fid in dict.fromkeys(order):
        f = BY_ID[fid]
        if fid in form or not applies(f, form, ctx) or _asked(asked, fid):
            continue
        if fid == "drug_allergies" and form.get("no_known_allergies"):
            continue
        if fid == "parental_and_family_history" and form.get("family_history_none_known"):
            continue
        if fid == "onset_date" and form.get("onset_note"):
            continue
        out.append(fid)
    # a home reading's device comes right after the warning signs
    n = next((i for i, f in enumerate(out) if f not in RED_FLAG_FIELDS and f != "main_symptoms_narrative"), len(out))
    return out[:n] + devices + out[n:]


def _always(fid: str) -> bool:
    return fid in RED_FLAG_FIELDS or fid.startswith(DEVICE) or fid in ESSENTIAL or fid == "main_symptoms_narrative"


def _todo(state: dict, ctx: dict) -> list[str]:
    """missing_fields(), cut short: at most MAX_QUESTIONS detail questions in all; warning signs, home-reading devices
    and the ESSENTIAL questions are always asked."""
    missing = missing_fields(state["form"], ctx, state["asked"])
    room = max(MAX_QUESTIONS - state["n"], 0)
    out = []
    for m in missing:
        if _always(m):
            out.append(m)
        elif room > 0:
            out.append(m)
            room -= 1
    return out


def probe_pool(form: dict, asked: dict, probes_used: int) -> list[str]:
    """Unmentioned symptoms the AI may ask about to tell possible causes apart (a limited number per conversation)."""
    if probes_used >= MAX_PROBES or not form.get("main_symptoms_narrative"):
        return []
    return [t for t in SYMPTOM_TOGGLES if t not in form and not _asked(asked, t)]


def red_flag_state(form: dict) -> tuple[bool, list[str]]:
    on = [f for f in RED_FLAG_FIELDS if form.get(f) is True]
    return bool(on), on


# ---------------------------------------------------------------------------
# Natural fixed questions (used when the AI is unavailable or its question fails the checks)
# ---------------------------------------------------------------------------
QUESTIONS = {
    "main_symptoms_narrative": "What's been bothering you? Tell me in your own words.",
    "onset_date": "When did this start? Roughly is fine, like “3 days ago”.",
    "trend": "Since it started, has it been getting better, staying the same, or getting worse?",
    "pain_severity_0_10": "If 0 is no pain and 10 is the worst you can imagine, where would you put it?",
    "pain_location": "Where exactly do you feel it?",
    "fever_present": "Have you had a fever with this?",
    "fever_pattern": "How does the fever behave? Is it there all the time, or does it come and go?",
    "highest_temp": "Have you checked your temperature? What was the highest reading?",
    "chills": "Have you had any chills or shivering?",
    "sweating": "Have you been sweating a lot?",
    "appetite": "How has your appetite been?",
    "stools_per_day": "How many times a day are you passing stools?",
    "bristol_scale": "What are the stools like: hard, normal, soft, or watery?",
    "urination_freq": "Roughly how many times a day are you passing urine?",
    "weight_loss_3m": "Have you lost any weight recently without trying?",
    "pregnancy_possible": "Is there any chance you could be pregnant?",
    "chest_pain": "Are you having any pain or pressure in your chest right now?",
    "severe_breathlessness": "Are you finding it very hard to breathe, even when resting?",
    "confusion_fainting": "Have you fainted, or felt very confused or drowsy at any point?",
    "uncontrolled_bleeding": "Have you had any bleeding that won't stop, or vomited any blood?",
    "fluid_intolerance_low_urine": "Are you able to keep water down, and passing urine as usual?",
    "seizure_or_stiff_neck": "Has your neck felt stiff, or have you had any fits?",
    "travel_30d_3m": "Have you travelled anywhere in the last few months?",
    "travel_3d": "Have you travelled anywhere in the last 3 days?",
    "outside_food_72h": "Have you eaten outside home in the last 3 days?",
    "untreated_water": "Have you had any unboiled or untreated water recently?",
    "sick_contact": "Has anyone around you been unwell recently?",
    "household_sick_count": "Is anyone at home having something similar? How many people?",
    "insect_animal_contact": "Any insect bites, lots of mosquitoes, or contact with animals in the last two weeks?",
    "parental_and_family_history": ("Has anyone in your family, especially your parents, had health problems like thyroid "
                                    "problems, diabetes, high blood pressure, heart problems or anything that runs in the family?"),
    "family_history_changed": "Has anyone in your family, like your parents, been diagnosed with anything new since your last visit?",
    "records_conditions_changed": "Your records mention {conditions}. Has anything changed with that recently?",
    "records_medicines_still_taking": "Your records show {medicines}. Have you been taking them regularly, or missed any?",
    "gender": "May I ask your sex?",
    "dob": "What's your date of birth?",
    "drug_allergies": "Are you allergic to any medicines or foods?",
    "current_medicines": "Do you take any medicines regularly? If so, which ones, and how often?",
    "chronic_conditions": "Has a doctor ever told you that you have a long-term condition, like diabetes or high blood pressure?",
    "smoking": "Do you smoke, or did you smoke in the past?",
    "alcohol": "Do you drink alcohol? If so, how often?",
    "height_cm": "How tall are you?",
    "weight_kg": "And roughly how much do you weigh?",
    "location": "Which city, town or village do you live in?",
    "occupation_category": "What kind of work do you do?",
    "residence_type": "Do you live in a city, a small town, or a village?",
    "water_source": "Where does your drinking water come from: tap, borewell, a filter, or bottled?",
    "work_exposure_note": "At work, are you around dust, chemicals, fumes, heat or loud noise?",
    "ppe_used": "Do you use any protective gear at work, like a mask or gloves?",
    "spicy_fried_freq": "How often do you eat spicy or fried food?",
    "high_risk_drugs": "In the last month, have you taken any painkillers, steroids, blood thinners or antibiotics?",
    "otc_herbal": "Have you tried any home remedies, herbal medicines or medicines from the chemist for this?",
    "lesion_or_rash_description": "Can you describe the rash: where it is, its colour, and whether it itches or hurts?",
    "home_spo2": "Have you checked your oxygen level? What did it show?",
    "home_bp": "Have you checked your blood pressure recently? What was it?",
    "home_hr": "Have you checked your pulse? What was it?",
    "home_glucose": "Have you checked your blood sugar? What was the reading?",
    "activity_level": "How active are you on a normal day?",
    "avg_sleep_hours": "How many hours do you usually sleep at night?",
    "consent_processing": "Thank you, that's really helpful. May we save your answers for your care and update your health profile with them?",
    "preferred_language": "Last one: which language would you like to use with the doctor?",
}
DEVICE_QUESTION = ("What did you use to measure that {what}? For example a BP machine with an arm cuff, a pulse oximeter, "
                   "a thermometer, a smartwatch or a fitness band.")


def fixed_question(target: str, ctx: dict) -> str:
    if target.startswith(DEVICE):
        return DEVICE_QUESTION.format(what=VITALS[target[len(DEVICE):]]["label"].lower() + " reading")
    f = BY_ID[target]
    text = QUESTIONS.get(target) or (f"Have you also noticed any {f['label'][0].lower() + f['label'][1:]}?" if f.get("symptom")
                                     else f"Could you tell me about this: {f['label'].lower()}?")
    return text.format(conditions=", ".join(ctx.get("conditions") or []), medicines=", ".join(ctx.get("medicines") or []))


def chips_for(target: str) -> list[str]:
    if target.startswith(DEVICE):
        return ["BP machine with arm cuff", "Pulse oximeter", "Thermometer", "Smartwatch", "Fitness band", "Don't remember"]
    f = BY_ID[target]
    if f["kind"] == "bool":
        return ["Yes", "No", "Not sure"]
    if f["kind"] in ("enum", "multi") and len(f["options"]) <= 8:
        return [o["label"] for o in f["options"]]
    if target == "pain_severity_0_10":
        return [str(n) for n in range(0, 11)]
    return []


URGENT_TEXT = ("Thank you for telling me. Please don't wait for this appointment: call 108 (ambulance) or go to the "
               "nearest emergency department now. If you still send this request, your doctor will be alerted to review it.")
CHECK_TEXT = {
    "chest_pain": "Just to be sure I understood: are you having chest pain or pressure yourself, right now?",
    "severe_breathlessness": "Just to check: are you yourself finding it very hard to breathe right now?",
    "confusion_fainting": "Just to check: have you yourself fainted or felt very confused or drowsy recently?",
    "uncontrolled_bleeding": "Just to check: are you yourself having bleeding that won't stop, or vomiting blood?",
    "fluid_intolerance_low_urine": "Just to check: are you yourself unable to keep fluids down, or passing very little urine?",
    "seizure_or_stiff_neck": "Just to check: have you yourself had a fit, or a stiff neck with fever, recently?",
}


# ---------------------------------------------------------------------------
# The AI turn
# ---------------------------------------------------------------------------
SYSTEM_PROMPT = """You are the intake assistant on a clinic's booking page. You talk with the patient in a warm,
natural way and quietly fill in their intake record for the doctor.

Strict rules:
- Never name, suggest, hint at or rule out any disease, condition or cause, and never explain why you ask something.
  You may privately think about what could explain the symptoms, only to choose a good question. Never write it.
- Never say whether something is serious or not, never reassure, never give advice (medicines, tests, home care).
- If asked what they have or what to do, say the doctor will go through that at the visit, then continue.
- Ask ONE short, kind, specific question at a time. Never list several things, never write a checklist or a form.
- Fill only what the patient clearly said about themselves, quoting their exact words. Never guess.
- Reply with JSON only, in exactly the format you are given."""

_HYPOTHESIS = re.compile("|".join([
    r"\byou (may|might|could|probably|likely) (have|be suffering)", r"sounds like", r"could be", r"might be", r"may be due",
    r"\blikely\b", r"\bprobably\b", r"diagnos", r"\bcaused? by\b", r"\bsuggests?\b", r"\bindicat", r"\bsign of\b", r"symptoms? of",
    r"\brule out\b", r"\bpossib(le|ly) (cause|reason)", r"\bbecause (this|that|it) (can|could|may)", r"\bserious\b",
    r"nothing to worry", r"\bdon'?t worry", r"\bshould\b", r"\brecommend", r"\badvis", r"\btry (to|taking|some)\b",
    r"\btake (a|an|some|it|this|paracetamol|medicine|tablets?)\b", r"\bdose\b", r"\bmg\b", r"paracetamol", r"ibuprofen",
    r"antibiotic", r"\btreat", r"\bcure", r"safety check", r"any of (these|the following)", r"checklist", r"\bfollowing\b",
]), re.I)
_DISEASE = re.compile("|".join([
    r"dengue", r"malaria", r"typhoid", r"covid", r"influenza", r"\bflu\b", r"infection", r"viral", r"bacteri", r"migraine",
    r"pneumonia", r"tubercul", r"\btb\b", r"\buti\b", r"gastr", r"append", r"heart attack", r"stroke", r"cancer", r"tumou?r",
    r"jaundice", r"hepatitis", r"cholera", r"chikungunya", r"thyroid", r"diabet", r"anaemi", r"anemi", r"hypertension",
    r"asthma", r"\bcopd\b", r"thalass", r"sickle", r"\bdisease", r"\bsyndrome", r"\bdisorder", r"\billness", r"\bcondition",
]), re.I)
# Questions about the family or the patient's own known conditions may name conditions (that is the question).
HISTORY_TARGETS = {"parental_and_family_history", "family_history_changed", "chronic_conditions", "records_conditions_changed",
                   "records_medicines_still_taking", "carrier_status", "current_medicines"}


def guard(text, *, target: str | None = None, max_len=300) -> str | None:
    """AI text that is safe to show: one question at most, no cause or likelihood language, no advice, no checklist,
    and no condition names unless the question is about family or already-known conditions."""
    if not isinstance(text, str):
        return None
    t = " ".join(text.split()).strip().strip('"')
    if not 2 <= len(t) <= max_len or t.count("?") > 1 or "http" in t or "{" in t or re.search(r"(^|\s)[-•*]\s|\d\)", t):
        return None
    if _HYPOTHESIS.search(t) or (target not in HISTORY_TARGETS and _DISEASE.search(t)):
        return None
    return t


_HEDGE = re.compile(r"\b(maybe|may ?be|might|not sure|unsure|perhaps|possibly|i think|i guess|probably|shayad|pata nahi)\b", re.I)
# Fields about a time window: from the AI only when the question was about that window.
TIME_WINDOW = {"outside_food_72h", "meal_type", "travel_3d", "travel_3d_destination", "insect_animal_contact",
               "high_risk_drugs", "weight_loss_3m"}


def _norm(t: str) -> str:
    return re.sub(r"[^a-z0-9 ]", "", " ".join(str(t).lower().split()))


def evidenced(updates, messages: list[dict], targets: list[str]) -> dict:
    """The AI's form updates backed by the patient's own words: each needs a quote that really appears in what the
    patient wrote, without hedging. Time-window fields need the question to have been about them. A warning sign
    quoted about someone else or the past is not taken."""
    if not isinstance(updates, dict):
        return {}
    said = _norm(" ".join(m["text"] for m in messages if m["role"] == "patient")[-3000:])
    out = {}
    for fid, u in updates.items():
        if not isinstance(u, dict) or fid not in BY_ID:
            continue
        q = u.get("quote") or ""
        if len(_norm(q)) < 2 or _norm(q) not in said or _HEDGE.search(q):
            continue
        if fid in TIME_WINDOW and fid not in targets:
            continue
        if BY_ID[fid].get("red_flag") and u.get("value") is True and (_OTHER_PERSON.search(q) or _PAST.search(q)):
            continue
        out[fid] = u.get("value")
    return out


def _schema_line(fid: str) -> str:
    if fid.startswith(DEVICE):
        v = fid[len(DEVICE):]
        return f"- {fid}: which device measured the {VITALS[v]['label'].lower()} (fill it as {v}.source_device)"
    f = BY_ID[fid]
    extra = ""
    if f["kind"] == "enum":
        extra = " one of " + "|".join(o["value"] for o in f["options"])
    elif f["kind"] == "multi":
        extra = " list of " + "|".join(o["value"] for o in f["options"])
    elif f["kind"] == "list":
        extra = " list of {" + ",".join(i["id"] for i in f["item_fields"]) + "}"
        if f.get("condition_hints"):
            extra += " (conditions e.g. " + ", ".join(f["condition_hints"]) + ")"
    elif f["kind"] == "vital":
        extra = ' {"value", "unit": ' + "|".join(VITALS[fid]["units"]) + ', "source_device"}'
    elif f["kind"] in ("int", "num") and "min" in f:
        extra = f" {f['min']}-{f['max']}"
    elif f["kind"] == "date":
        extra = " YYYY-MM-DD"
    return f"- {f['id']} ({f['kind']}{extra}): {f['label']}"


ALWAYS_FILLABLE = {"travel_3d", "travel_3d_destination", "travel_30d_3m", "travel_30d_3m_destination", "outside_food_72h",
                   "meal_type", "untreated_water", "sick_contact", "household_sick_count", "current_medicines",
                   "drug_allergies", "chronic_conditions", "smoking", "alcohol", "occupation_category", "pregnancy_possible",
                   "reports_to_upload", "otc_herbal", "otc_herbal_names", "high_risk_drugs", "parental_and_family_history",
                   "family_history_none_known", "onset_note", "pain_location", "other_symptoms", *VITALS, *RED_FLAG_FIELDS}


def _ai_turn(llm_factory, form: dict, ctx: dict, messages: list[dict], must: str | None, choices: list[str],
             probes: list[str]) -> dict | None:
    if llm_factory is None:
        return None
    fillable = [f["id"] for f in FIELDS if applies({**f, "only_if": None}, form, ctx)
                and (f["id"] not in form or f["kind"] in ("vital", "list", "tags"))
                and (f["section"] in ("phase2", "toggles") or f["id"] in choices or f["id"] in ALWAYS_FILLABLE)]
    convo = "\n".join(f"{'Patient' if m['role'] == 'patient' else 'Assistant'}: {m['text']}" for m in messages[-12:])
    known = {k: v for k, v in form.items() if k != "last_known_labs"}
    if must:
        ask = f"You MUST ask about this next, in your own natural words:\n{_schema_line(must)}\n"
    else:
        ask = ("Choose the ONE most useful next question. Usually take one of these, best first:\n"
               + "\n".join(_schema_line(c) for c in choices[:5]) + "\n")
        if probes:
            ask += ("Or, if your private picture of what could explain the symptoms means a symptom the patient has NOT "
                    "mentioned would help tell the possibilities apart, ask about one of these instead:\n"
                    + "\n".join(_schema_line(p) for p in probes[:25]) + "\n")
    prompt = (
        f"Today is {date.today().isoformat()}. This is a {'returning' if ctx.get('returning') else 'new'} patient.\n"
        f"Already known (do not ask again): {json.dumps(known, ensure_ascii=False)[:2800]}\n\n"
        f"Conversation so far:\n{convo}\n\n"
        "Fields you may fill from the patient's latest message:\n" + "\n".join(_schema_line(f) for f in fillable[:80]) + "\n\n"
        + ask + "\n"
        "Fill EVERY field the patient's latest message clearly answers, not only the one that was asked. Examples: "
        "'my brother at home has the same' -> sick_contact true, household_sick_count 1; 'my mother has thyroid' -> "
        "parental_and_family_history [{relation: mother, condition: Thyroid problem}]; 'BP was 150/95 on my Omron' -> "
        "home_bp {value: 150/95, source_device: Omron}. Do not fill what they were unsure about ('maybe', 'not sure'), "
        "or what was about someone else, or time-limited fields unless the timing fits.\n\n"
        "Answer as JSON:\n"
        '{"form_updates": {field: {"value": value, "quote": "the patient\'s exact words that say it"}, ...},\n'
        ' "assistant_message": "a brief, warm acknowledgement if fitting, then ONE question",\n'
        ' "target_field": "the field your question asks about",\n'
        ' "quick_replies": ["up to 5 short answer chips"]}'
    )
    try:
        raw = llm_factory().complete(SYSTEM_PROMPT, prompt, 800)
    except LLMUnavailableError as e:
        log.info("Intake AI unavailable (%s); using fixed questions.", e.code)
        return None
    except Exception:
        log.exception("Intake AI failed; using fixed questions.")
        return None
    m = re.search(r"\{.*\}", raw or "", re.S)
    try:
        out = json.loads(m.group(0)) if m else None
    except ValueError:
        out = None
    return out if isinstance(out, dict) else None


# ---------------------------------------------------------------------------
# One turn
# ---------------------------------------------------------------------------
def _target_ok(k: str) -> bool:
    return k in BY_ID or (k.startswith(DEVICE) and k[len(DEVICE):] in VITALS)


def _clean_state(raw) -> dict:
    raw = raw if isinstance(raw, dict) else {}
    msgs = [{"role": m.get("role"), "text": str(m.get("text", ""))[:1000]} for m in (raw.get("messages") or [])
            if isinstance(m, dict) and m.get("role") in ("patient", "assistant")][-MAX_MESSAGES:]
    return {"form": clean_form(raw.get("form")), "messages": msgs,
            "asked": {k: int(v) for k, v in (raw.get("asked") or {}).items() if _target_ok(k) and isinstance(v, (int, float))},
            "targets": [t for t in (raw.get("targets") or []) if _target_ok(t)][:2],
            "check": [s for s in (raw.get("check") or []) if s in RED_FLAG_FIELDS],
            "probes": int(raw["probes"]) if isinstance(raw.get("probes"), (int, float)) else 0,
            "n": int(raw["n"]) if isinstance(raw.get("n"), (int, float)) else 0,
            "sources": {k: v for k, v in (raw.get("sources") or {}).items() if k in BY_ID and v in ("records", "chat")}}


def _set(state: dict, fid: str, value) -> bool:
    f = BY_ID.get(fid)
    if not f or f.get("computed") or f.get("readonly"):
        return False
    old = state["form"].get(fid)
    v = _valid(f, value, old)
    if v is None:
        return False
    if f["kind"] == "multi" and isinstance(old, list) and v != ["none"]:
        v = [x for x in dict.fromkeys(old + v) if x != "none"]
    if f["kind"] == "list" and isinstance(old, list):
        seen = {json.dumps(r, sort_keys=True).lower() for r in old}
        v = old + [r for r in v if json.dumps(r, sort_keys=True).lower() not in seen]
    if f["kind"] == "tags" and isinstance(old, list):
        v = list(dict.fromkeys(old + v))
    state["form"][fid] = v
    state["sources"][fid] = "chat"
    return True


_YES = re.compile(r"^\s*(y|yes|yeah|yep|haan?|ha|ji|sure|correct|right|i do|i have|i did)\b", re.I)
_NO = re.compile(r"^\s*(n|no|nope|nahi?n?|na|never|none|not really|i don'?t|i haven'?t|i didn'?t)\b", re.I)
_UNSURE = re.compile(r"not sure|don'?t know|unsure|no idea|can'?t say|pata nahi|don'?t remember", re.I)


def _answer_target(state: dict, target: str, message: str) -> bool:
    """Deterministic reading of a direct answer to the question just asked (quick replies arrive as text)."""
    m = message.strip()
    if target.startswith(DEVICE):
        fid = target[len(DEVICE):]
        dev = re.sub(r"^(?:(?:it was |i used |i use )?(?:on|with|using|by|from) )?(?:my |a |the |an )?", "", m, flags=re.I)
        return isinstance(state["form"].get(fid), dict) and _set(state, fid, {"source_device": (dev or m)[:80]})
    f = BY_ID[target]
    has_unsure_option = f["kind"] == "enum" and any(o["value"] in ("unsure", "not_sure") for o in f["options"])
    if _UNSURE.search(m) and not has_unsure_option:
        return False
    if f["kind"] == "bool":
        if _YES.search(m):
            return _set(state, target, True)
        if _NO.search(m):
            return _set(state, target, False)
        return False
    if f["kind"] in ("enum", "multi"):
        low = m.lower()
        for o in f["options"]:
            if low in (o["label"].lower(), o["value"].lower()):
                return _set(state, target, o["value"] if f["kind"] == "enum" else [o["value"]])
        if f["kind"] == "multi" and _NO.search(m) and any(o["value"] == "none" for o in f["options"]):
            return _set(state, target, ["none"])
        return False
    if f["kind"] in ("int", "num") and (n := re.search(r"\b(\d{1,3}(?:\.\d+)?)\b", m)):
        return _set(state, target, float(n.group(1)))
    if f["kind"] == "vital" and (n := re.search(r"\d{2,3}(?:\s*/\s*\d{2,3}|\.\d)?", m)):
        return _set(state, target, {"value": n.group(0)})
    if target == "drug_allergies" and _NO.search(m):
        return _set(state, "no_known_allergies", True)
    if target == "parental_and_family_history" and _NO.search(m):
        return _set(state, "family_history_none_known", True)
    if target == "current_medicines" and _NO.search(m):
        state["form"]["current_medicines"] = [{"drug_name": "None", "dose": "", "frequency": "", "reason": ""}]
        return True
    if f["kind"] == "text" and target != "main_symptoms_narrative" and len(m) >= 2 and not _NO.search(m):
        return _set(state, target, m)
    return False


def _resolved(state: dict, t: str) -> bool:
    if t.startswith(DEVICE):
        return bool((state["form"].get(t[len(DEVICE):]) or {}).get("source_device"))
    return t in state["form"]


def turn(db: Session, user: User, raw_state, message: str | None, llm_factory) -> dict:
    if user.patient is None:
        raise AppError(403, "FORBIDDEN_ROLE", "Only patients can use the intake chat.")
    state = _clean_state(raw_state)
    records, ctx = hydrate(db, user.patient)
    if not isinstance(raw_state, dict) or "form" not in raw_state:  # first turn: start from the records
        state["form"] = records
        state["sources"] = {k: "records" for k in ctx["from_records"]}
    elif records.get("last_known_labs"):
        state["form"]["last_known_labs"] = records["last_known_labs"]  # read-only: always from the reports
    before = json.loads(json.dumps(state["form"]))
    ai_out = None
    message = (message or "").strip()[:1000]

    if message:
        state["messages"].append({"role": "patient", "text": message})
        if "main_symptoms_narrative" in state["form"]:
            state["n"] += 1
        targets = state["targets"]
        for t in targets:
            _answer_target(state, t, message)
        if "main_symptoms_narrative" not in state["form"]:
            _set(state, "main_symptoms_narrative", message)
        patch, now, check = rule_patch(message)
        for fid, v in sorted(patch.items(), key=lambda kv: bool(BY_ID[kv[0]].get("only_if"))):
            if fid not in state["form"] or fid in targets or BY_ID[fid]["kind"] in ("vital", "list"):
                _set(state, fid, v)
        for fid in now:
            _set(state, fid, True)
        for fid in check:
            if fid not in state["form"] and fid not in state["check"]:
                state["check"].append(fid)
        if "onset_date" in targets and "onset_date" not in state["form"] and _TIMEISH.search(message):
            _set(state, "onset_note", message)  # "past few days, not sure exactly": kept in their words
        for t in targets:
            if t in state["check"]:  # the "just to check" question was answered
                state["check"].remove(t)
                state["form"].setdefault(t, False)
            if not _resolved(state, t):
                state["asked"][t] = state["asked"].get(t, 0) + 1
        compute(state["form"])

    halted, flags_on = red_flag_state(state["form"])
    missing = _todo(state, ctx)
    must = state["check"][0] if state["check"] else None
    if not must and missing and (missing[0] in RED_FLAG_FIELDS or missing[0].startswith(DEVICE)
                                 or missing[0] in ("main_symptoms_narrative", "onset_date", "trend")):
        must = missing[0]
    probes = [] if must or state["n"] >= MAX_QUESTIONS else probe_pool(state["form"], state["asked"], state["probes"])

    if message and not halted:
        ai_out = _ai_turn(llm_factory, state["form"], ctx, state["messages"], must, missing, probes)
        if ai_out:
            ups = evidenced(ai_out.get("form_updates"), state["messages"], state["targets"])
            for fid, v in sorted(ups.items(), key=lambda kv: bool(BY_ID[kv[0]].get("only_if"))):
                if fid not in state["form"] or fid in state["targets"] or state["sources"].get(fid) == "chat" \
                        or BY_ID[fid]["kind"] in ("vital", "list", "tags"):
                    _set(state, fid, v)
            compute(state["form"])
            halted, flags_on = red_flag_state(state["form"])
            missing = _todo(state, ctx)
            if must and _resolved(state, must):
                must = None

    # the next question
    chips: list[str] = []
    target = None
    if halted:
        text = URGENT_TEXT
    elif state["check"]:
        target = state["check"][0]
        text, chips = CHECK_TEXT[target], ["Yes", "No"]
    elif "main_symptoms_narrative" not in state["form"]:
        target = "main_symptoms_narrative"
        name = ctx["name"]
        text = (f"Hello {name}, welcome back. I have your records, so I'll only ask what's new. What's been bothering you?"
                if ctx["returning"] else f"Hello {name}! I'm here to help your doctor prepare for your visit. What's been bothering you?")
    elif not missing:
        text = "Thank you, that's all I needed to know about the problem. Just a few quick questions left."
    else:
        text = None
        allowed = [must] if must else missing[:5] + probes
        if ai_out and isinstance(ai_out.get("target_field"), str) and ai_out["target_field"] in allowed \
                and not _resolved(state, ai_out["target_field"]):
            tf = ai_out["target_field"]
            msg = guard(ai_out.get("assistant_message"), target=tf)
            if msg:
                text, target = msg, tf
                chips = chips_for(tf) or [c for c in (ai_out.get("quick_replies") or [])[:5]
                                          if isinstance(c, str) and guard(c, target=tf, max_len=40)]
                if tf in probes and tf not in missing:
                    state["probes"] += 1
        if text is None:
            target = must if must and not _resolved(state, must) else missing[0]
            text, chips = fixed_question(target, ctx), chips_for(target)
    state["targets"] = [target] if target else []
    state["messages"].append({"role": "assistant", "text": text})
    state["messages"] = state["messages"][-MAX_MESSAGES:]
    after = state["form"]
    updates = {k: after[k] for k in after if json.dumps(before.get(k), sort_keys=True) != json.dumps(after[k], sort_keys=True)}
    return {
        "assistant_message": text,
        "quick_replies": chips,
        "silent_form_updates": updates,
        "extracted_clinical_codes": codes(after),
        "red_flag_triggered": halted,
        "red_flags": [BY_ID[f]["label"] for f in flags_on],
        "booking_answers": booking_answers(after),
        "context": {k: ctx[k] for k in ("returning", "name", "conditions", "medicines", "last_booking")},
        "done": halted or (not missing and not state["check"] and "main_symptoms_narrative" in after),
        "ai_used": bool(ai_out),
        "remaining": len(missing) + len(state["check"]),  # chat questions still to come (roughly)
        "state": state,
    }


# ---------------------------------------------------------------------------
# Outputs
# ---------------------------------------------------------------------------
def codes(form: dict) -> list[dict]:
    out, seen = [], set()
    for fid, (display, snomed, icd) in CODES.items():
        if form.get(fid) is True and display not in seen:
            seen.add(display)
            out.append({"field": fid, "display": display, "snomed_ct": snomed or None, "icd10": icd or None,
                        "source": "fixed code table; for the doctor to verify"})
    return out


def booking_answers(form: dict) -> dict:
    """Values for the existing booking questions that the intake answers exactly (anything inexact is left)."""
    out = {}
    d = form.get("duration_days")
    if d is not None:
        out["duration"] = "today" if d == 0 else "1_3_days" if d <= 3 else "4_7_days" if d <= 7 else "1_4_weeks" if d <= 28 else "over_month"
    if form.get("smoking"):
        out["smoking"] = {"current": "now", "former": "former", "never": "never"}[form["smoking"]]
    cc = form.get("chronic_conditions") or []
    if "diabetes" in cc:
        out["diabetes"] = "yes"
    elif cc == ["none"]:
        out["diabetes"] = "no"
    if form.get("chest_pain") is True or form.get("chest_discomfort") is True:
        out["chest_pain"] = "yes"
    elif form.get("chest_pain") is False and form.get("chest_discomfort") is False:
        out["chest_pain"] = "no"
    if form.get("pregnancy_possible") is not None:
        out["pregnant"] = "yes" if form["pregnancy_possible"] else "no"
    if form.get("location"):
        match = next((c for c, *_ in cities.CITIES if c.lower() == form["location"].strip().lower()), None)
        if match:
            out["city"] = match
    if form.get("travel_3d") is False and form.get("travel_30d_3m") is False:
        out["travel"] = "no"
    if form.get("gender") in ("male", "female"):
        out["sex"] = form["gender"]
    return out


def _display(f: dict, v) -> str:
    if f["kind"] == "vital":
        s = f"{v.get('value')} {v.get('unit', '')}".strip()
        if v.get("source_device"):
            s += f" · {v['source_device']} · reliability {v['reliability_score']:.2f} ({TIERS[v['reliability_tier']]})"
        else:
            s += " · device not given"
        return s
    if f["kind"] == "bool":
        return "Yes" if v else "No"
    if f["kind"] == "enum":
        return next((o["label"] for o in f["options"] if o["value"] == v), str(v))
    if f["kind"] == "multi":
        return ", ".join(next((o["label"] for o in f["options"] if o["value"] == x), x) for x in v)
    if f["kind"] == "tags":
        return ", ".join(v)
    if f["kind"] == "list":
        return "; ".join(" · ".join(x for x in row.values() if x) for row in v)
    return f"{v:g}" if isinstance(v, float) else str(v)


def serialize_record(r: IntakeRecord) -> dict:
    """For the doctor: filled fields grouped by section, the codes, and any red flags."""
    data = r.data or {}
    sections = []
    for s in SECTIONS:
        items = [{"field": f["id"], "label": f["label"], "value": _display(f, data[f["id"]])}
                 for f in FIELDS if f["section"] == s["id"] and f["id"] in data]
        if items:
            sections.append({"id": s["id"], "title": s["title"], "items": items})
    on = [BY_ID[f]["label"] for f in RED_FLAG_FIELDS if data.get(f) is True]
    return {"id": r.id, "appointment_id": r.appointment_id, "created_at": r.created_at.isoformat(), "sections": sections,
            "codes": r.codes or [], "red_flag": r.red_flag, "red_flags": on}


def summary_line(r: IntakeRecord) -> str:
    """One line for the doctor's AI facts list: yes/no symptoms and timing from the intake."""
    d = r.data or {}
    keys = ["fever_present", *SYMPTOM_TOGGLES]
    yes = [BY_ID[f]["label"].lower() for f in keys if d.get(f) is True]
    no = [BY_ID[f]["label"].lower() for f in keys if d.get(f) is False]
    bits = []
    if yes:
        bits.append("has: " + ", ".join(yes))
    if no:
        bits.append("does not have: " + ", ".join(no))
    if d.get("onset_date"):
        bits.append(f"started {d['onset_date']}")
    if d.get("trend"):
        bits.append(f"trend: {_display(BY_ID['trend'], d['trend'])}")
    return "Patient's intake answers: " + "; ".join(bits)


# ---------------------------------------------------------------------------
# Saving (when the booking is sent)
# ---------------------------------------------------------------------------
PROFILE_SKIP = {"drug_allergies", "no_known_allergies", "chronic_conditions", "current_medicines", "prior_surgeries",
                "parental_and_family_history", "gender", "dob"}  # stored in their own tables


def save(db: Session, user: User, appointment_id: str | None, raw_form) -> IntakeRecord | None:
    """Save the intake with the booking and fill gaps in the patient's profile. Only with consent; without it nothing
    is saved. Values already on the profile are never overwritten or erased."""
    form = clean_form(raw_form)
    if form.get("consent_processing") is not True:
        return None
    p: Patient = user.patient
    flag, _ = red_flag_state(form)
    rec = IntakeRecord(patient_id=p.id, appointment_id=appointment_id, data=form, codes=codes(form), red_flag=flag)
    db.add(rec)
    base = db.get(PatientBaseline, p.id) or PatientBaseline(patient_id=p.id, data={})
    merged = dict(base.data or {})
    for f in FIELDS:
        if (f.get("baseline") or f["section"] == "phase5") and f["id"] in form and f["id"] not in PROFILE_SKIP:
            merged[f["id"]] = form[f["id"]]
    base.data, base.updated_at = merged, now_utc()
    db.add(base)
    if not p.date_of_birth and form.get("dob"):
        p.date_of_birth = date.fromisoformat(form["dob"])
    if not (p.gender or "").strip() and form.get("gender") in ("male", "female", "other"):
        p.gender = form["gender"].capitalize()
    db.commit()
    db.refresh(rec)
    _sync_history(db, user, form)
    return rec


def _sync_history(db: Session, user: User, form: dict) -> None:
    """New allergies, conditions, medicines, operations and family history go to the health background page."""
    pid = user.patient.id
    items = db.scalars(select(HealthHistoryItem).where(HealthHistoryItem.patient_id == pid,
                                                       HealthHistoryItem.removed_at.is_(None))).all()
    have = {(i.kind, i.name.strip().lower()) for i in items}
    rx = {r.medication.strip().lower() for r in db.scalars(select(Prescription).where(Prescription.patient_id == pid))}
    note = "Told the intake chat"

    def add(kind, name, detail=None):
        name = (name or "").strip()[:200]
        if len(name) >= 2 and name.lower() != "none" and (kind, name.lower()) not in have:
            history.add_item(db, user, pid, kind, name, detail)
            have.add((kind, name.lower()))

    for a in form.get("drug_allergies") or []:
        add("ALLERGY", a, note)
    if form.get("no_known_allergies") and not any(k in ("ALLERGY", history.NKA) for k, _ in have) and not form.get("drug_allergies"):
        history.add_item(db, user, pid, history.NKA, None, note)
    labels = {o["value"]: o["label"] for o in BY_ID["chronic_conditions"]["options"]}
    known = " ".join(n for k, n in have if k == "CONDITION")
    for c in form.get("chronic_conditions") or []:
        pat = dict(_CONDITION_WORDS).get(c)
        if c in ("none", "others") or (pat and re.search(pat, known, re.I)):
            continue
        add("CONDITION", labels[c], note)
    for m in form.get("current_medicines") or []:
        if m.get("drug_name", "").strip().lower() not in rx:
            add("MEDICATION", f"{m.get('drug_name', '')} {m.get('dose', '')}".strip(),
                " · ".join(x for x in (m.get("frequency"), m.get("reason")) if x) or note)
    for s in form.get("prior_surgeries") or []:
        add("SURGERY", s.get("type"), s.get("year") or None)
    for fh in form.get("parental_and_family_history") or []:
        rel = " ".join(x for x in (fh.get("relation"), f"at {fh['age_at_onset']}" if fh.get("age_at_onset") else "") if x)
        add("FAMILY", fh.get("condition"), rel or None)


def latest_record(db: Session, patient_id: str) -> IntakeRecord | None:
    return db.scalar(select(IntakeRecord).where(IntakeRecord.patient_id == patient_id)
                     .order_by(IntakeRecord.created_at.desc()).limit(1))


def for_appointment(db: Session, appointment_id: str) -> IntakeRecord | None:
    return db.scalar(select(IntakeRecord).where(IntakeRecord.appointment_id == appointment_id))


def context_payload(db: Session, user: User) -> dict:
    if user.patient is None:
        raise AppError(403, "FORBIDDEN_ROLE", "Only patients can use the intake chat.")
    form, ctx = hydrate(db, user.patient)
    return {"form": form, "context": ctx, "booking_answers": booking_answers(form)}
