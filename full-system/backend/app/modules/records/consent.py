"""Patient consent: granting / revoking a doctor's access, and doctors' requests for access.

Consent alone decides access (see access_control.py). A doctor who has no access can send one request;
the patient approves (which grants consent) or declines it. Notifications carry no clinical details and
never the doctor's written reason, which is shown only inside the patient's portal.
"""

from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.models import (
    ConsentRequest,
    ConsentRequestStatus,
    ConsentStatus,
    Doctor,
    Patient,
    PatientDoctorConsent,
    VerificationStatus,
)
from app.modules.appointments.service import notify

# After a decline the same doctor must wait this long before asking again.
DECLINE_COOLDOWN = timedelta(days=7)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def set_consent(db: Session, patient_id: str, doctor_id: str, grant: bool) -> PatientDoctorConsent:
    """Grant or revoke. Granting also closes the doctor's open request, if any. Commits."""
    if db.get(Doctor, doctor_id) is None:
        raise AppError(404, "DOCTOR_NOT_FOUND", "Doctor not found.")
    now = _now()
    row = db.scalar(select(PatientDoctorConsent).where(
        PatientDoctorConsent.patient_id == patient_id, PatientDoctorConsent.doctor_id == doctor_id))
    if row is None:
        row = PatientDoctorConsent(patient_id=patient_id, doctor_id=doctor_id, status=ConsentStatus.REVOKED)
        db.add(row)
    if grant:
        row.status, row.granted_at, row.revoked_at = ConsentStatus.GRANTED, now, None
        pending = _pending(db, patient_id, doctor_id)
        if pending:
            pending.status, pending.responded_at = ConsentRequestStatus.APPROVED, now
    else:
        row.status, row.revoked_at = ConsentStatus.REVOKED, now
    db.commit()
    return row


def _pending(db: Session, patient_id: str, doctor_id: str) -> ConsentRequest | None:
    return db.scalar(select(ConsentRequest).where(
        ConsentRequest.patient_id == patient_id, ConsentRequest.doctor_id == doctor_id,
        ConsentRequest.status == ConsentRequestStatus.PENDING))


def _latest(db: Session, patient_id: str, doctor_id: str) -> ConsentRequest | None:
    return db.scalar(select(ConsentRequest).where(
        ConsentRequest.patient_id == patient_id, ConsentRequest.doctor_id == doctor_id,
    ).order_by(ConsentRequest.created_at.desc(), ConsentRequest.id.desc()).limit(1))


def request_state(db: Session, doctor_id: str, patient_id: str, has_access: bool) -> dict:
    """What the doctor sees about asking this patient for access."""
    last = _latest(db, patient_id, doctor_id)
    out = {"status": last.status.value if last else None,
           "requested_at": last.created_at.isoformat() if last else None,
           "responded_at": last.responded_at.isoformat() if last and last.responded_at else None,
           "can_request": False, "retry_after": None}
    if has_access or (last and last.status == ConsentRequestStatus.PENDING):
        return out
    if last and last.status == ConsentRequestStatus.DECLINED and last.responded_at:
        retry = last.responded_at + DECLINE_COOLDOWN
        if retry > _now():
            out["retry_after"] = retry.isoformat()
            return out
    out["can_request"] = True
    return out


def create_request(db: Session, doctor: Doctor, patient_id: str, reason: str | None) -> ConsentRequest:
    """Doctor asks for access. The caller has checked the doctor has no access yet. Commits."""
    patient = db.get(Patient, patient_id)
    if patient is None or not patient.user.is_active:
        raise AppError(404, "PATIENT_NOT_FOUND", "Patient not found.")
    if doctor.verification_status != VerificationStatus.VERIFIED or not doctor.user.is_active:
        raise AppError(403, "DOCTOR_NOT_VERIFIED", "Only verified doctors can request access.")
    state = request_state(db, doctor.id, patient_id, has_access=False)
    if state["status"] == ConsentRequestStatus.PENDING.value:
        raise AppError(409, "REQUEST_PENDING", "You have already asked this patient. Wait for their answer.")
    if not state["can_request"]:
        raise AppError(409, "REQUEST_RECENTLY_DECLINED",
                       "The patient declined your last request. You can ask again after 7 days.",
                       retry_after=state["retry_after"])
    req = ConsentRequest(patient_id=patient_id, doctor_id=doctor.id, reason=(reason or "").strip()[:300] or None)
    db.add(req)
    notify(db, patient.user_id, "CONSENT_REQUESTED", f"{doctor.full_name} asked to see your health records",
           "Open Doctor access to allow or decline.", "/patient/consent")
    db.commit()
    return req


def pending_for_patient(db: Session, patient_id: str) -> list[dict]:
    rows = db.scalars(select(ConsentRequest).where(
        ConsentRequest.patient_id == patient_id, ConsentRequest.status == ConsentRequestStatus.PENDING,
    ).order_by(ConsentRequest.created_at)).all()
    return [{
        "id": r.id,
        "doctor": {"id": r.doctor.id, "name": r.doctor.full_name, "specialization": r.doctor.specialization,
                   "hospital": r.doctor.hospital.name if r.doctor.hospital else None},
        "reason": r.reason,
        "requested_at": r.created_at.isoformat(),
    } for r in rows]


def respond(db: Session, patient_id: str, request_id: int, approve: bool) -> ConsentRequest:
    """Patient approves (grants consent) or declines a pending request. Commits."""
    req = db.get(ConsentRequest, request_id)
    if req is None or req.patient_id != patient_id:
        raise AppError(404, "REQUEST_NOT_FOUND", "Request not found.")
    if req.status != ConsentRequestStatus.PENDING:
        raise AppError(409, "REQUEST_CLOSED", "This request has already been answered.")
    patient = db.get(Patient, patient_id)
    if approve:
        set_consent(db, patient_id, req.doctor_id, grant=True)  # also marks the request APPROVED
        notify(db, req.doctor.user_id, "CONSENT_APPROVED", f"{patient.full_name} allowed you to see their records",
               link=f"/doctor/patients/{patient_id}")
    else:
        req.status, req.responded_at = ConsentRequestStatus.DECLINED, _now()
        notify(db, req.doctor.user_id, "CONSENT_DECLINED", f"{patient.full_name} declined your access request",
               link=f"/doctor/patients/{patient_id}")
    db.commit()
    return req
