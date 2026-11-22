"""Visit intake: symptoms and vital signs.

Who writes what:
- PATIENT: the reason for the visit when booking (appointments.reason, shown here as the patient's entry).
- RECEPTION (front desk / nurse): at check-in, the patient's own words, red-flag checklist and measured vitals.
  Reception only records; it never sees medical records, earlier visits or the booking reason.
- DOCTOR: "additional symptoms" the patient missed. A new entry; nobody edits someone else's entry.

Who can read a visit's intake: that appointment's doctor and the patient (no record consent needed, because the
patient booked this doctor). Reading intake across visits (e.g. in Decision Support) needs record access (consent).
"""

from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.models import Appointment, AppointmentStatus, Role, SymptomEntry, User, VitalSigns
from app.modules.appointments.service import _utc, notify, now_utc, zone

RED_FLAGS = {
    "CHEST_PAIN_SWEATING": "Chest pain with sweating or breathlessness",
    "BREATHLESS_AT_REST": "Breathless at rest or can't finish a sentence",
    "FAINTING": "Fainted or nearly fainted",
    "STROKE_SIGNS": "Sudden face droop, arm weakness or slurred speech",
    "CONFUSION": "New confusion or very drowsy",
    "SEVERE_BLEEDING": "Heavy bleeding (vomiting blood, black stools or other)",
    "SEIZURE": "Seizure (fit)",
    "FEVER_RASH_NECK": "High fever with a rash that doesn't fade, or a stiff neck",
}
# Measured values that are dangerous on their own (checked in addition to the checklist).
VITAL_FLAGS = (
    ("spo2", lambda v: v < 90, "Oxygen saturation below 90%"),
    ("systolic_bp", lambda v: v < 90, "Systolic BP below 90"),
    ("systolic_bp", lambda v: v >= 180, "Systolic BP 180 or higher"),
    ("pulse", lambda v: v > 130 or v < 40, "Pulse above 130 or below 40"),
    ("temperature_c", lambda v: v >= 40, "Temperature 40 °C or higher"),
)
VITAL_FIELDS = ("systolic_bp", "diastolic_bp", "pulse", "temperature_c", "spo2", "weight_kg", "height_cm")
VITALS_MAX_AGE = timedelta(days=90)  # older vitals are not used to pre-fill risk scores
CHECK_IN_STATUSES = (AppointmentStatus.REQUESTED, AppointmentStatus.CONFIRMED)


# ---------------------------------------------------------------------------
# Serializers
# ---------------------------------------------------------------------------
def serialize_entry(e: SymptomEntry) -> dict:
    codes = [c for c in (e.red_flags or "").split(",") if c]
    return {"id": e.id, "appointment_id": e.appointment_id, "author_role": e.author_role,
            "author_name": e.author.full_name, "text": e.text, "duration": e.duration, "severity": e.severity,
            "red_flags": [{"code": c, "label": RED_FLAGS.get(c, c)} for c in codes], "created_at": _utc(e.created_at)}


def serialize_vitals(v: VitalSigns) -> dict:
    out = {f: getattr(v, f) for f in VITAL_FIELDS}
    out.update(id=v.id, appointment_id=v.appointment_id, recorded_by_role=v.recorded_by_role,
               recorded_by_name=v.recorded_by.full_name, measured_at=_utc(v.measured_at),
               warnings=vital_warnings(out))
    return out


def vital_warnings(values: dict) -> list[str]:
    return [label for field, bad, label in VITAL_FLAGS if values.get(field) is not None and bad(values[field])]


def _booking_entry(db: Session, a: Appointment) -> dict | None:
    """The patient's words when booking, with how long / how bad / warning signs from the booking questions."""
    if not a.reason:
        return None
    from app.modules.booking import questionnaire  # avoids a circular import

    ans = questionnaire.for_appointment(db, a.id)
    duration = questionnaire.DURATIONS.get(ans.duration) if ans else None
    codes = [c for c in ((ans.red_flags if ans else None) or "").split(",") if c]
    return {"id": f"booking-{a.id}", "appointment_id": a.id, "author_role": "PATIENT",
            "author_name": a.patient.full_name, "text": a.reason, "duration": duration,
            "severity": ans.severity if ans else None,
            "red_flags": [{"code": c, "label": RED_FLAGS.get(c, c)} for c in codes],
            "created_at": _utc(a.created_at), "from_booking": True}


# ---------------------------------------------------------------------------
# Reception
# ---------------------------------------------------------------------------
def _local_day_bounds(tz_name: str | None, day: str | None) -> tuple[datetime, datetime]:
    tz = zone(tz_name or "Asia/Kolkata")
    d = datetime.fromisoformat(day).date() if day else now_utc().astimezone(tz).date()
    start = datetime(d.year, d.month, d.day, tzinfo=tz)
    return start, start + timedelta(days=1)


def todays_appointments(db: Session, tz_name: str | None, day: str | None = None) -> list[dict]:
    """Identity, time and doctor only (no booking reason, no records), plus what reception recorded."""
    start, end = _local_day_bounds(tz_name, day)
    rows = db.scalars(select(Appointment).where(
        Appointment.start_at >= start, Appointment.start_at < end,
        Appointment.status.in_(CHECK_IN_STATUSES + (AppointmentStatus.COMPLETED,)),
    ).order_by(Appointment.start_at)).all()
    out = []
    for a in rows:
        entries = db.scalars(select(SymptomEntry).where(SymptomEntry.appointment_id == a.id,
                                                        SymptomEntry.author_role == Role.RECEPTION.value)
                             .order_by(SymptomEntry.created_at)).all()
        vitals = db.scalars(select(VitalSigns).where(VitalSigns.appointment_id == a.id,
                                                     VitalSigns.recorded_by_role == Role.RECEPTION.value)
                            .order_by(VitalSigns.measured_at)).all()
        out.append({
            "id": a.id, "start_at": _utc(a.start_at), "end_at": _utc(a.end_at), "status": a.status.value,
            "doctor": {"id": a.doctor.id, "name": a.doctor.full_name, "specialization": a.doctor.specialization},
            "patient": {"id": a.patient.id, "name": a.patient.full_name, "gender": a.patient.gender},
            "checked_in": bool(entries or vitals),
            "can_check_in": a.status in CHECK_IN_STATUSES,
            "entries": [serialize_entry(e) for e in entries],
            "vitals": [serialize_vitals(v) for v in vitals],
        })
    return out


def check_in(db: Session, user: User, appointment_id: str, body: dict, tz_name: str | None) -> dict:
    """Reception records the patient's words, red flags and vitals for today's appointment. Commits."""
    a = db.get(Appointment, appointment_id)
    start, end = _local_day_bounds(tz_name, None)
    if a is None or not (start <= a.start_at < end):
        raise AppError(404, "APPOINTMENT_NOT_FOUND", "No appointment with this id today.")
    if a.status not in CHECK_IN_STATUSES:
        raise AppError(409, "INVALID_STATE", f"This appointment is {a.status.value.lower()}; check-in is not possible.")
    text = (body.get("symptoms") or "").strip()
    flags = [c for c in dict.fromkeys(body.get("red_flags") or []) if c in RED_FLAGS]
    vitals = {f: body.get(f) for f in VITAL_FIELDS if body.get(f) is not None}
    if not text and not flags and not vitals:
        raise AppError(422, "EMPTY_CHECK_IN", "Enter the symptoms, a warning sign or at least one measurement.")
    entry = None
    if text or flags:
        entry = SymptomEntry(patient_id=a.patient_id, appointment_id=a.id, author_user_id=user.id,
                             author_role=Role.RECEPTION.value, text=text or "(no description, warning signs only)",
                             duration=(body.get("duration") or "").strip() or None,
                             severity=body.get("severity"), red_flags=",".join(flags) or None)
        db.add(entry)
    vs = None
    if vitals:
        vs = VitalSigns(patient_id=a.patient_id, appointment_id=a.id, recorded_by_user_id=user.id,
                        recorded_by_role=Role.RECEPTION.value, **vitals)
        db.add(vs)
    urgent = [RED_FLAGS[c] for c in flags] + vital_warnings(vitals)
    if urgent:
        # No clinical details in notifications: just "see this patient now" and a link to the appointment.
        notify(db, a.doctor.user_id, "URGENT_CHECK_IN", f"Urgent: please see {a.patient.full_name} now",
               "Warning signs were recorded at check-in.", f"/doctor/appointments?focus={a.id}")
    db.commit()
    return {"urgent": urgent, "entry": serialize_entry(entry) if entry else None,
            "vitals": serialize_vitals(vs) if vs else None}


# ---------------------------------------------------------------------------
# A single visit (its doctor and its patient)
# ---------------------------------------------------------------------------
def visit_appointment(db: Session, user: User, appointment_id: str) -> Appointment:
    a = db.get(Appointment, appointment_id)
    is_patient = user.role == Role.PATIENT and user.patient and a is not None and a.patient_id == user.patient.id
    is_doctor = user.role == Role.DOCTOR and user.doctor and a is not None and a.doctor_id == user.doctor.id
    if not (is_patient or is_doctor):
        raise AppError(404, "APPOINTMENT_NOT_FOUND", "Appointment not found.")
    return a


def visit_intake(db: Session, a: Appointment) -> dict:
    entries = db.scalars(select(SymptomEntry).where(SymptomEntry.appointment_id == a.id)
                         .order_by(SymptomEntry.created_at)).all()
    vitals = db.scalars(select(VitalSigns).where(VitalSigns.appointment_id == a.id)
                        .order_by(VitalSigns.measured_at)).all()
    from app.modules.booking import questionnaire
    items = [e for e in [_booking_entry(db, a)] if e] + [serialize_entry(e) for e in entries]
    ans = questionnaire.for_appointment(db, a.id)
    from app.modules.booking import intake_engine
    rec = intake_engine.for_appointment(db, a.id)
    return {"appointment_id": a.id, "patient": {"id": a.patient.id, "name": a.patient.full_name},
            "entries": items, "vitals": [serialize_vitals(v) for v in vitals],
            "answers": questionnaire.serialize(ans) if ans else None,
            "intake_record": intake_engine.serialize_record(rec) if rec else None,
            "urgent": sorted({f["label"] for e in items for f in e["red_flags"]}
                             | {w for v in vitals for w in vital_warnings({f: getattr(v, f) for f in VITAL_FIELDS})}
                             | set(intake_engine.serialize_record(rec)["red_flags"] if rec else []))}


def add_doctor_symptoms(db: Session, user: User, patient_id: str, appointment_id: str | None, text: str,
                        duration: str | None = None) -> SymptomEntry:
    """The doctor's "additional symptoms". The caller has checked the doctor may write for this patient. Commits."""
    e = SymptomEntry(patient_id=patient_id, appointment_id=appointment_id, author_user_id=user.id,
                     author_role=Role.DOCTOR.value, text=text.strip(), duration=(duration or "").strip() or None)
    db.add(e)
    db.commit()
    db.refresh(e)
    return e


# ---------------------------------------------------------------------------
# Across visits (needs record access; used by Decision Support)
# ---------------------------------------------------------------------------
def recent_intake(db: Session, patient_id: str, days: int = 30) -> dict:
    since = now_utc() - timedelta(days=days)
    entries = db.scalars(select(SymptomEntry).where(SymptomEntry.patient_id == patient_id,
                                                    SymptomEntry.created_at >= since)
                         .order_by(SymptomEntry.created_at)).all()
    appts = db.scalars(select(Appointment).where(Appointment.patient_id == patient_id, Appointment.created_at >= since,
                                                 Appointment.reason.is_not(None))
                       .order_by(Appointment.created_at)).all()
    items = sorted([e for e in (_booking_entry(db, a) for a in appts) if e] + [serialize_entry(e) for e in entries],
                   key=lambda e: e["created_at"])
    latest = latest_vitals(db, patient_id)
    from app.modules.booking import questionnaire
    from app.modules.booking import intake_engine
    ans = questionnaire.latest(db, patient_id)
    rec = intake_engine.latest_record(db, patient_id)
    return {"entries": items, "latest_vitals": serialize_vitals(latest) if latest else None,
            "answers": questionnaire.serialize(ans) if ans else None,
            "intake_record": intake_engine.serialize_record(rec) if rec else None,
            "urgent": sorted({f["label"] for e in items for f in e["red_flags"]}
                             | set(serialize_vitals(latest)["warnings"] if latest else []))}


def latest_vitals(db: Session, patient_id: str) -> VitalSigns | None:
    return db.scalar(select(VitalSigns).where(VitalSigns.patient_id == patient_id,
                                              VitalSigns.measured_at >= now_utc() - VITALS_MAX_AGE)
                     .order_by(VitalSigns.measured_at.desc()).limit(1))


def latest_from_patient(db: Session, patient_id: str) -> dict | None:
    """For the doctor's patient page: what the patient told us at their most recent booking (the booking questions
    and the intake chat), as a short summary, with when it was last updated. The caller has checked record access."""
    from app.modules.booking import intake_engine
    from app.modules.booking import questionnaire
    a = db.scalar(select(Appointment).where(Appointment.patient_id == patient_id, Appointment.reason.is_not(None))
                  .order_by(Appointment.created_at.desc()).limit(1))
    if a is None:
        return None
    visit = visit_intake(db, a)
    ans = questionnaire.for_appointment(db, a.id)
    rec = intake_engine.for_appointment(db, a.id)
    times = [_utc(a.created_at)] + [e["created_at"] for e in visit["entries"]] + [v["measured_at"] for v in visit["vitals"]]
    lines: list[str] = []
    booking = next((e for e in visit["entries"] if e.get("from_booking")), None)
    if booking:
        how = ", ".join(x for x in (booking["duration"] and booking["duration"].lower(), booking["severity"]) if x)
        lines.append(f"Problem: {booking['text']}" + (f" ({how})" if how else ""))
    lines.append("Warning signs: " + (", ".join(visit["urgent"]) if visit["urgent"] else "none reported"))
    if rec:
        d = rec.data or {}
        line = intake_engine.summary_line(rec).removeprefix("Patient's intake answers: ")
        if line:
            lines.append(line[0].upper() + line[1:])
        for fid in intake_engine.VITALS:
            if isinstance(d.get(fid), dict):
                lines.append(f"Home reading: {intake_engine.BY_ID[fid]['label']} "
                             f"{intake_engine._display(intake_engine.BY_ID[fid], d[fid])}")
    if ans:
        line = questionnaire.summary(ans).removeprefix("Patient's answers when booking: ")
        lines.append(line[:1].upper() + line[1:])
    return {"updated_at": max(times), "appointment": {"id": a.id, "start_at": _utc(a.start_at), "status": a.status.value,
                                                      "doctor": a.doctor.full_name if a.doctor else None},
            "summary": lines, "urgent": visit["urgent"], "answers": visit["answers"],
            "intake_record": visit["intake_record"], "vitals": visit["vitals"]}
