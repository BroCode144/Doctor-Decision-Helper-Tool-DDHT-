"""Booking questions: what the patient can answer without a test, used by the risk models and the doctor.

Asked (all required): symptoms, how long, how bad, warning signs, tobacco, diabetes / blood-pressure medicine they
were told about, chest pain (three plain follow-ups), pregnancy (profile female only), sex (only if the profile has
none), where they live and recent travel (city names only). Not asked, because a patient cannot answer them reliably: cholesterol, fasting sugar, ECG, exercise-test
results, measured BP (reception measures it), and the risk-equation group (left to the doctor).

Chest-pain type for the heart model is worked out from the three follow-ups with the Diamond-Forrester rule
(Diamond GA, Forrester JS. N Engl J Med 1979;300:1350-8), the definition used in the model's training data:
  central chest discomfort + brought on by effort or stress + eased by rest:  3 of 3 = typical angina,
  2 of 3 = atypical angina, 0-1 = non-anginal pain; no chest pain = asymptomatic.
If any follow-up is "not sure", no type is derived and the doctor chooses.
"""

from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.models import HealthAnswers, Patient
from app.modules.booking import cities
from app.modules.appointments.service import _utc, now_utc
from app.modules.booking.intake import RED_FLAGS

YNU = [{"value": "yes", "label": "Yes"}, {"value": "no", "label": "No"}, {"value": "unsure", "label": "Not sure"}]
YN = YNU[:2]
DURATIONS = {"today": "Started today", "1_3_days": "1-3 days", "4_7_days": "4-7 days", "1_4_weeks": "1-4 weeks",
             "over_month": "More than a month", "checkup": "No new problem (check-up or follow-up)"}
SEVERITIES = {"mild": "Mild: I can do my usual work", "moderate": "Moderate: it stops some of my work",
              "severe": "Severe: I can't do my usual work"}
SMOKING = {"now": "Yes, I smoke now", "former": "I used to, but stopped", "never": "Never"}
CP_TYPES = {1: "Typical angina", 2: "Atypical angina", 3: "Non-anginal pain", 4: "No chest pain"}
ANSWERS_MAX_AGE = timedelta(days=365)  # lifestyle answers older than this are not used
CHEST_PAIN_MAX_AGE = timedelta(days=90)  # chest-pain answers describe the current problem
TRAVEL_MAX_AGE = timedelta(days=30)  # "travelled in the last 3 weeks" only matters for the illness at that booking


def _needs_pregnancy(p: Patient) -> bool:
    return (p.gender or "").strip().lower() in ("female", "f")


def _needs_sex(p: Patient) -> bool:
    return (p.gender or "").strip().lower() not in ("female", "f", "male", "m")


def questions(p: Patient) -> dict:
    """The question list for this patient (the frontend renders it; validate() enforces the same list)."""
    qs = [
        {"id": "duration", "label": "How long have you had this?", "options": [{"value": k, "label": v} for k, v in DURATIONS.items()]},
        {"id": "severity", "label": "How bad is it?", "options": [{"value": k, "label": v} for k, v in SEVERITIES.items()],
         "skip_if": {"duration": "checkup"}},
        {"id": "smoking", "label": "Do you smoke (cigarettes, bidis, hookah)?", "options": [{"value": k, "label": v} for k, v in SMOKING.items()]},
        {"id": "diabetes", "label": "Has a doctor ever told you that you have diabetes (high blood sugar)?", "options": YNU},
        {"id": "bp_medicine", "label": "Do you take medicine for blood pressure?", "options": YNU},
        {"id": "chest_pain", "label": "In the last month, have you had pain or discomfort in your chest?", "options": YN},
        {"id": "cp_central", "label": "Is it in the middle of the chest, like pressure, tightness or heaviness?", "options": YNU,
         "only_if": {"chest_pain": "yes"}},
        {"id": "cp_exertion", "label": "Does it come on when you walk fast, climb stairs or are stressed?", "options": YNU,
         "only_if": {"chest_pain": "yes"}},
        {"id": "cp_rest_relief", "label": "Does it go away within about 10 minutes of resting?", "options": YNU,
         "only_if": {"chest_pain": "yes"}},
        {"id": "city", "kind": "city", "label": "Which city or town do you live in?", "options": cities.options()},
        {"id": "travel", "label": "In the last 3 weeks, have you travelled to another city, town or village?", "options": YN},
        {"id": "travel_city", "kind": "city", "label": "Where did you go? (the main place)", "options": cities.options(),
         "only_if": {"travel": "yes"}},
    ]
    if _needs_pregnancy(p):
        qs.append({"id": "pregnant", "label": "Are you pregnant?", "options": YNU})
    if _needs_sex(p):
        qs.append({"id": "sex", "label": "Sex (used by medical formulas; your profile doesn't have it)",
                   "options": [{"value": "male", "label": "Male"}, {"value": "female", "label": "Female"}]})
        qs.append({"id": "pregnant", "label": "Are you pregnant?", "options": YNU, "only_if": {"sex": "female"}})
    return {"questions": qs, "red_flags": [{"code": k, "label": v} for k, v in RED_FLAGS.items()],
            "nearest_max_km": cities.NEAREST_MAX_KM}


def _applies(q: dict, ans: dict) -> bool:
    if "only_if" in q and any(ans.get(k) != v for k, v in q["only_if"].items()):
        return False
    if "skip_if" in q and all(ans.get(k) == v for k, v in q["skip_if"].items()):
        return False
    return True


def validate(p: Patient, body: dict) -> dict:
    """Every question that applies must be answered with one of its options; red flags must be a list (empty =
    "none of these"). Returns only the answers that apply. Raises 422 naming what is missing."""
    qs = questions(p)["questions"]
    out, missing = {}, []
    for q in qs:
        if not _applies(q, body):
            continue
        v = body.get(q["id"])
        if v not in {o["value"] for o in q["options"]}:
            missing.append(q["label"])
        else:
            out[q["id"]] = v
    flags = body.get("red_flags")
    if not isinstance(flags, list) or any(c not in RED_FLAGS for c in flags):
        missing.append("Warning signs (tick any, or 'None of these')")
    else:
        out["red_flags"] = list(dict.fromkeys(flags))
    if missing:
        raise AppError(422, "QUESTIONS_INCOMPLETE", "Please answer: " + "; ".join(missing))
    return out


def save(db: Session, patient_id: str, appointment_id: str, ans: dict) -> HealthAnswers:
    row = HealthAnswers(patient_id=patient_id, appointment_id=appointment_id, duration=ans["duration"],
                        severity=ans.get("severity"), red_flags=",".join(ans["red_flags"]) or None,
                        smoking=ans["smoking"], diabetes=ans["diabetes"], bp_medicine=ans["bp_medicine"],
                        chest_pain=ans["chest_pain"], cp_central=ans.get("cp_central"), cp_exertion=ans.get("cp_exertion"),
                        cp_rest_relief=ans.get("cp_rest_relief"), pregnant=ans.get("pregnant"), sex=ans.get("sex"),
                        city=ans.get("city"), travel=ans.get("travel"), travel_city=ans.get("travel_city"))
    db.add(row)
    return row


def chest_pain_type(a: HealthAnswers) -> tuple[int | None, str]:
    """(model value 1-4 or None, explanation)."""
    if a.chest_pain == "no":
        return 4, "no chest pain in the last month"
    parts = {"central pressure-like": a.cp_central, "brought on by effort or stress": a.cp_exertion,
             "eased by rest": a.cp_rest_relief}
    if any(v != "yes" and v != "no" for v in parts.values()):
        return None, "the patient was not sure about some chest-pain questions"
    n = sum(v == "yes" for v in parts.values())
    t = 1 if n == 3 else 2 if n == 2 else 3
    said = ", ".join(f"{k}: {v}" for k, v in parts.items())
    return t, f"{said} ({n} of 3 features)"


def latest(db: Session, patient_id: str) -> HealthAnswers | None:
    return db.scalar(select(HealthAnswers).where(HealthAnswers.patient_id == patient_id,
                                                 HealthAnswers.created_at >= now_utc() - ANSWERS_MAX_AGE)
                     .order_by(HealthAnswers.created_at.desc()).limit(1))


def for_appointment(db: Session, appointment_id: str) -> HealthAnswers | None:
    return db.scalar(select(HealthAnswers).where(HealthAnswers.appointment_id == appointment_id))


def is_recent_for_chest_pain(a: HealthAnswers) -> bool:
    return now_utc() - _created(a) <= CHEST_PAIN_MAX_AGE


def _created(a: HealthAnswers):
    return a.created_at if a.created_at.tzinfo else a.created_at.replace(tzinfo=now_utc().tzinfo)


def places(a: HealthAnswers | None) -> list[tuple[str, str]]:
    """(city, why) from the answers: where the patient lives, and where they travelled if the booking is recent."""
    out = []
    if a and a.city and a.city != cities.OTHER:
        out.append((a.city, "where the patient lives"))
    if a and a.travel == "yes" and a.travel_city and a.travel_city != cities.OTHER and now_utc() - _created(a) <= TRAVEL_MAX_AGE:
        out.append((a.travel_city, "the patient travelled there in the 3 weeks before booking"))
    return out


def _place(v: str | None) -> str | None:
    return "not in the list" if v == cities.OTHER else v


def label(field: str, value: str | None) -> str | None:
    if value is None:
        return None
    if field == "duration":
        return DURATIONS.get(value, value)
    if field == "severity":
        return value
    if field == "smoking":
        return {"now": "smokes now", "former": "stopped smoking", "never": "never smoked"}.get(value, value)
    return {"yes": "yes", "no": "no", "unsure": "not sure"}.get(value, value)


def serialize(a: HealthAnswers) -> dict:
    t, why = chest_pain_type(a)
    rows = [("How long", DURATIONS.get(a.duration, a.duration)),
            ("How bad", a.severity),
            ("Smoking", label("smoking", a.smoking)),
            ("Told they have diabetes", label("diabetes", a.diabetes)),
            ("Takes blood-pressure medicine", label("bp_medicine", a.bp_medicine)),
            ("Chest pain in the last month", label("chest_pain", a.chest_pain)),
            ("Chest pain: central, pressure-like", label("cp_central", a.cp_central)),
            ("Chest pain: brought on by effort or stress", label("cp_exertion", a.cp_exertion)),
            ("Chest pain: eased by rest", label("cp_rest_relief", a.cp_rest_relief)),
            ("Pregnant", label("pregnant", a.pregnant)),
            ("Sex", a.sex),
            ("Lives in", _place(a.city)),
            ("Travelled in the 3 weeks before booking", label("travel", a.travel)),
            ("Travelled to", _place(a.travel_city))]
    return {"id": a.id, "appointment_id": a.appointment_id, "created_at": _utc(a.created_at),
            "items": [{"label": k, "value": v} for k, v in rows if v],
            "chest_pain_type": {"value": t, "label": CP_TYPES.get(t), "why": why} if t else None,
            "red_flags": [{"code": c, "label": RED_FLAGS.get(c, c)} for c in (a.red_flags or "").split(",") if c]}


def summary(a: HealthAnswers) -> str:
    """One line for the AI facts list."""
    bits = [label("smoking", a.smoking), f"told they have diabetes: {label('diabetes', a.diabetes)}",
            f"takes blood-pressure medicine: {label('bp_medicine', a.bp_medicine)}",
            f"chest pain in the last month: {a.chest_pain}"]
    t, why = chest_pain_type(a)
    if a.chest_pain == "yes":
        bits.append(f"chest pain details: {why}")
    if a.pregnant:
        bits.append(f"pregnant: {label('pregnant', a.pregnant)}")
    if a.city:
        bits.append(f"lives in: {_place(a.city)}")
    if a.travel == "yes":
        bits.append(f"travelled in the 3 weeks before booking, to: {_place(a.travel_city)}")
    elif a.travel == "no":
        bits.append("no travel in the 3 weeks before booking")
    return "Patient's answers when booking: " + "; ".join(bits)
