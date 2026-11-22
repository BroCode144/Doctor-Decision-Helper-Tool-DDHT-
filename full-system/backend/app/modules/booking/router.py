"""Check-in (reception), visit symptoms and vitals, health background, and local disease patterns (admin)."""

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, require_roles
from app.core.errors import AppError
from app.db.session import get_db
from app.models import Appointment, LocalDiseasePattern, Role, User
from app.schemas import CheckInRequest, HistoryItemCreate, LocalDiseaseCreate, SymptomsAdd
from app.modules.records import history as history_svc
from app.modules.booking import intake as svc
from app.shared.access_control import resolve_patient_context
from app.shared.audit import Action, Result, audit

router = APIRouter(tags=["intake"])
reception_only = require_roles(Role.RECEPTION)


# ---------------------------------------------------------------------------
# Reception: today's list and check-in (identity + what reception records; no records, no booking reason)
# ---------------------------------------------------------------------------
@router.get("/reception/appointments")
def reception_appointments(tz: str | None = Query(None, max_length=64), day: str | None = Query(None, max_length=10),
                           user: User = Depends(reception_only), db: Session = Depends(get_db)):
    return {"red_flags": svc.RED_FLAGS, "appointments": svc.todays_appointments(db, tz, day)}


@router.post("/reception/appointments/{appointment_id}/check-in", status_code=201)
def reception_check_in(appointment_id: str, body: CheckInRequest, request: Request,
                       tz: str | None = Query(None, max_length=64),
                       user: User = Depends(reception_only), db: Session = Depends(get_db)):
    unknown = [c for c in body.red_flags if c not in svc.RED_FLAGS]
    if unknown:
        raise AppError(422, "UNKNOWN_RED_FLAG", f"Unknown warning sign: {', '.join(unknown)}.")
    out = svc.check_in(db, user, appointment_id, body.model_dump(), tz)
    appt = db.get(Appointment, appointment_id)
    audit(Action.CHECK_IN_RECORDED, Result.SUCCESS, user=user, patient_id=appt.patient_id,
          resource_type="appointment", resource_id=appointment_id,
          reason="urgent warning signs" if out["urgent"] else None, request=request)
    return out


# ---------------------------------------------------------------------------
# One visit: its doctor and its patient (no record consent needed; the patient booked this doctor)
# ---------------------------------------------------------------------------
@router.get("/appointments/{appointment_id}/intake")
def visit_intake(appointment_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return svc.visit_intake(db, svc.visit_appointment(db, user, appointment_id))


@router.post("/appointments/{appointment_id}/symptoms", status_code=201)
def visit_add_symptoms(appointment_id: str, body: SymptomsAdd, request: Request,
                       user: User = Depends(require_roles(Role.DOCTOR)), db: Session = Depends(get_db)):
    a = svc.visit_appointment(db, user, appointment_id)
    e = svc.add_doctor_symptoms(db, user, a.patient_id, a.id, body.text, body.duration)
    audit(Action.SYMPTOMS_ADDED, Result.SUCCESS, user=user, patient_id=a.patient_id,
          resource_type="appointment", resource_id=a.id, request=request)
    return svc.serialize_entry(e)


# ---------------------------------------------------------------------------
# Across visits: needs record access (doctor with consent, or the patient)
# ---------------------------------------------------------------------------
@router.get("/patients/{patient_id}/intake")
def patient_intake(patient_id: str, request: Request, user: User = Depends(get_current_user),
                   db: Session = Depends(get_db)):
    ctx = resolve_patient_context(db, user, patient_id, "intake_view", request,
                                  allowed_roles=(Role.DOCTOR, Role.PATIENT), log_grant=False)
    return svc.recent_intake(db, ctx.patient_id)


@router.post("/patients/{patient_id}/symptoms", status_code=201)
def patient_add_symptoms(patient_id: str, body: SymptomsAdd, request: Request,
                         user: User = Depends(require_roles(Role.DOCTOR)), db: Session = Depends(get_db)):
    ctx = resolve_patient_context(db, user, patient_id, "symptoms_add", request, allowed_roles=(Role.DOCTOR,))
    if body.appointment_id:
        a = db.get(Appointment, body.appointment_id)
        if a is None or a.patient_id != ctx.patient_id or a.doctor_id != user.doctor.id:
            raise AppError(404, "APPOINTMENT_NOT_FOUND", "Appointment not found.")
    e = svc.add_doctor_symptoms(db, user, ctx.patient_id, body.appointment_id, body.text, body.duration)
    audit(Action.SYMPTOMS_ADDED, Result.SUCCESS, user=user, patient_id=ctx.patient_id,
          resource_type="symptom_entry", resource_id=str(e.id), request=request)
    return svc.serialize_entry(e)


@router.get("/patients/{patient_id}/latest-from-patient")
def latest_from_patient(patient_id: str, request: Request, user: User = Depends(require_roles(Role.DOCTOR)),
                        db: Session = Depends(get_db)):
    """The doctor's "Latest from the patient" card: a summary of the most recent booking's answers."""
    ctx = resolve_patient_context(db, user, patient_id, "intake_view", request, allowed_roles=(Role.DOCTOR,), log_grant=False)
    return {"latest": svc.latest_from_patient(db, ctx.patient_id)}


# ---------------------------------------------------------------------------
# Health background (allergies, surgeries, conditions, family history)
# ---------------------------------------------------------------------------
def _history_ctx(db, user, patient_id, purpose, request):
    return resolve_patient_context(db, user, patient_id, purpose, request,
                                   allowed_roles=(Role.DOCTOR, Role.PATIENT), log_grant=False)


@router.get("/patients/{patient_id}/history")
def get_history(patient_id: str, request: Request, user: User = Depends(get_current_user),
                db: Session = Depends(get_db)):
    ctx = _history_ctx(db, user, patient_id, "history_view", request)
    return history_svc.health_history(db, ctx.patient_id)


@router.post("/patients/{patient_id}/history", status_code=201)
def add_history(patient_id: str, body: HistoryItemCreate, request: Request, user: User = Depends(get_current_user),
                db: Session = Depends(get_db)):
    ctx = _history_ctx(db, user, patient_id, "history_add", request)
    item = history_svc.add_item(db, user, ctx.patient_id, body.kind, body.name, body.detail)
    audit(Action.RECORD_CREATED, Result.SUCCESS, user=user, patient_id=ctx.patient_id,
          resource_type="health_history", resource_id=str(item.id), reason=item.kind, request=request)
    return history_svc.health_history(db, ctx.patient_id)


@router.delete("/patients/{patient_id}/history/{item_id}")
def remove_history(patient_id: str, item_id: int, request: Request, user: User = Depends(get_current_user),
                   db: Session = Depends(get_db)):
    ctx = _history_ctx(db, user, patient_id, "history_remove", request)
    item = history_svc.remove_item(db, user, ctx.patient_id, item_id)
    audit(Action.RECORD_STATUS_CHANGED, Result.SUCCESS, user=user, patient_id=ctx.patient_id,
          resource_type="health_history", resource_id=str(item.id), reason=f"{item.kind} removed", request=request)
    return history_svc.health_history(db, ctx.patient_id)


# ---------------------------------------------------------------------------
# Local disease patterns (admin): context for "conditions to consider"
# ---------------------------------------------------------------------------
def _serialize_pattern(p: LocalDiseasePattern) -> dict:
    return {"id": p.id, "city": p.city, "disease": p.disease, "start_month": p.start_month, "end_month": p.end_month,
            "level": p.level, "source": p.source, "note": p.note}


@router.get("/admin/local-diseases")
def list_local_diseases(user: User = Depends(require_roles(Role.ADMIN)), db: Session = Depends(get_db)):
    rows = db.scalars(select(LocalDiseasePattern).order_by(LocalDiseasePattern.city, LocalDiseasePattern.start_month))
    return [_serialize_pattern(p) for p in rows]


@router.post("/admin/local-diseases", status_code=201)
def add_local_disease(body: LocalDiseaseCreate, request: Request, user: User = Depends(require_roles(Role.ADMIN)),
                      db: Session = Depends(get_db)):
    p = LocalDiseasePattern(**body.model_dump(), created_by_user_id=user.id)
    p.city, p.disease = p.city.strip(), p.disease.strip()
    db.add(p)
    db.commit()
    audit(Action.ADMIN_OPERATION, Result.SUCCESS, user=user, resource_type="local_disease_pattern",
          resource_id=str(p.id), reason=f"{p.city}: {p.disease}", request=request)
    return _serialize_pattern(p)


@router.delete("/admin/local-diseases/{pattern_id}")
def delete_local_disease(pattern_id: int, request: Request, user: User = Depends(require_roles(Role.ADMIN)),
                         db: Session = Depends(get_db)):
    p = db.get(LocalDiseasePattern, pattern_id)
    if p is None:
        raise AppError(404, "NOT_FOUND", "Not found.")
    db.delete(p)
    db.commit()
    audit(Action.ADMIN_OPERATION, Result.SUCCESS, user=user, resource_type="local_disease_pattern",
          resource_id=str(pattern_id), reason="deleted", request=request)
    return {"deleted": pattern_id}
