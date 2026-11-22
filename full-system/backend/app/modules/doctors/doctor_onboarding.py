"""Doctor applications: apply with documents -> automatic check -> admin decision -> email -> set password -> sign in.

- No account exists before approval, so an unapproved doctor cannot sign in at all.
- Documents are checked in the background (reading a photo takes a few seconds). If a file is clearly the wrong kind
  of document, or shows a full Aadhaar number, the doctor is asked to re-upload it automatically (NEEDS_INFO);
  everything else goes to the admin queue with a checklist.
- Emailed links are one-time and expire: re-upload (7 days), set password (48 hours). Only a hash of each token is
  stored, and the token is put after '#' in the link so it never reaches server logs.
- The photo ID file is deleted once the admin has decided (approve or reject).
"""

import hashlib
import json
import logging
import secrets
import uuid
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import AppError
from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models import Doctor, DoctorVerification, Hospital, Role, User, VerificationStatus
from app.models.doctor_onboarding import ApplicationDocument, ApplicationStatus as S, DoctorApplication, OneTimeLink
from app.modules.doctors import councils
from app.modules.doctors import doctor_documents as dd
from app.modules.doctors import doctor_mail
from app.shared.document_processing import validate_upload
from app.shared.storage import get_storage

log = logging.getLogger("ddht.doctor_onboarding")
SET_PASSWORD_TTL = timedelta(hours=48)
REUPLOAD_TTL = timedelta(days=7)
MAX_SETUP_LINKS_PER_HOUR = 3


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _aware(t: datetime) -> datetime:
    return t if t.tzinfo else t.replace(tzinfo=timezone.utc)


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


@dataclass
class UploadedFile:
    kind: str
    filename: str | None
    content_type: str | None
    data: bytes


# ---------------------------------------------------------------------------
# One-time links
# ---------------------------------------------------------------------------
def _new_link(db: Session, purpose: str, ttl: timedelta, *, user_id: str | None = None, application_id: str | None = None) -> str:
    # an older unused link for the same thing stops working
    q = update(OneTimeLink).where(OneTimeLink.purpose == purpose, OneTimeLink.used_at.is_(None))
    q = q.where(OneTimeLink.user_id == user_id) if user_id else q.where(OneTimeLink.application_id == application_id)
    db.execute(q.values(used_at=_now()))
    token = secrets.token_urlsafe(32)
    db.add(OneTimeLink(purpose=purpose, token_hash=_hash(token), user_id=user_id, application_id=application_id,
                       expires_at=_now() + ttl))
    return token


def _link_url(path: str, token: str, origin: str | None = None) -> str:
    base = (origin or get_settings().public_app_url).rstrip("/")
    return f"{base}{path}#token={token}"


def _valid_link(db: Session, purpose: str, token: str) -> OneTimeLink:
    row = db.scalar(select(OneTimeLink).where(OneTimeLink.token_hash == _hash(token or ""), OneTimeLink.purpose == purpose))
    if row is None or row.used_at is not None:
        raise AppError(400, "LINK_INVALID", "This link is not valid or has already been used.")
    if _aware(row.expires_at) < _now():
        raise AppError(400, "LINK_EXPIRED", "This link has expired.")
    return row


# ---------------------------------------------------------------------------
# Applying
# ---------------------------------------------------------------------------
def _store(db: Session, app: DoctorApplication, f: UploadedFile) -> ApplicationDocument:
    if f.kind not in dd.KINDS:
        raise AppError(422, "INVALID_DOCUMENT_KIND", "Unknown document type.")
    v = validate_upload(f.filename, f.content_type, f.data, get_settings().max_upload_bytes)
    key = f"applications/{app.id}/{uuid.uuid4().hex}{v.extension}"
    get_storage().save(key, f.data)
    for old in app.documents:
        if old.kind == f.kind and not old.superseded:
            old.superseded = True
    doc = ApplicationDocument(application_id=app.id, kind=f.kind, original_filename=v.display_name, storage_path=key,
                              mime_type=v.mime_type, size_bytes=len(f.data), sha256=hashlib.sha256(f.data).hexdigest())
    app.documents.append(doc)
    return doc


def submit(db: Session, fields: dict, files: list[UploadedFile]) -> DoctorApplication:
    email = fields["email"].strip().lower()
    if db.scalar(select(User.id).where(func.lower(User.email) == email)):
        raise AppError(409, "EMAIL_TAKEN", "An account with this email already exists. Please sign in.")
    if db.scalar(select(DoctorApplication.id).where(func.lower(DoctorApplication.email) == email,
                                                    DoctorApplication.status.in_((S.CHECKING, S.UNDER_REVIEW, S.NEEDS_INFO)))):
        raise AppError(409, "APPLICATION_OPEN", "There is already an open application for this email. Check its status instead.")
    if fields["council"] not in councils.COUNCILS:
        raise AppError(422, "INVALID_COUNCIL", "Choose your medical council from the list.")
    if not (1950 <= fields["registration_year"] <= date.today().year):
        raise AppError(422, "INVALID_YEAR", "Registration year is not valid.")
    if fields.get("hospital_id") and db.get(Hospital, fields["hospital_id"]) is None:
        raise AppError(422, "INVALID_HOSPITAL", "Unknown hospital.")
    kinds = [f.kind for f in files]
    need = ["REGISTRATION", "DEGREE", "PHOTO_ID"] + (["PG_DEGREE"] if fields.get("claims_specialist") else [])
    missing = [dd.KINDS[k] for k in need if k not in kinds]
    if missing:
        raise AppError(422, "DOCUMENTS_MISSING", "Please upload: " + "; ".join(missing))
    if len(set(kinds)) != len(kinds):
        raise AppError(422, "DUPLICATE_DOCUMENT", "Upload one file for each document.")
    app = DoctorApplication(**{**fields, "email": email, "full_name": fields["full_name"].strip(),
                               "registration_number": fields["registration_number"].strip().upper()})
    db.add(app)
    db.flush()
    try:
        for f in files:
            _store(db, app, f)
        db.commit()
    except Exception:
        db.rollback()
        for d in app.documents:
            if d.storage_path:
                get_storage().delete(d.storage_path) if get_storage().exists(d.storage_path) else None
        raise
    db.refresh(app)
    doctor_mail.received(app.email, app.full_name, app.id)
    return app


def run_checks(application_id: str) -> None:
    """Background job: read and check every new file, then route the application. Uses its own DB session."""
    db = SessionLocal()
    try:
        app = db.get(DoctorApplication, application_id)
        if app is None or app.status != S.CHECKING:
            return
        storage = get_storage()
        for d in app.documents:
            if d.superseded or d.check_result:
                continue
            text, method = dd.read(storage.read(d.storage_path), d.mime_type, d.kind)
            d.read_method = method
            d.read_text = None if d.kind == "PHOTO_ID" else (text[:20000] if text else None)  # never keep ID text
            d.check_result = json.dumps(dd.check_document(app, d.kind, text, method))
        db.flush()
        summ = dd.summary(db, app)
        app.check_summary = json.dumps(summ)
        if summ["blocks"]:
            app.status = S.NEEDS_INFO
            app.info_request = json.dumps({"kinds": [b["kind"] for b in summ["blocks"]], "message": None, "by": "automatic check"})
            token = _new_link(db, "REUPLOAD", REUPLOAD_TTL, application_id=app.id)
            db.commit()
            doctor_mail.needs_info(app.email, app.full_name, app.id, [f"{b['title']}: {b['reason']}" for b in summ["blocks"]],
                                   None, _link_url("/doctor/reupload", token))
        else:
            app.status = S.UNDER_REVIEW
            db.commit()
    except Exception:
        log.exception("Checking application %s failed", application_id)
        db.rollback()
        app = db.get(DoctorApplication, application_id)
        if app is not None and app.status == S.CHECKING:
            app.status = S.UNDER_REVIEW  # never stuck: the admin checks by eye
            db.commit()
    finally:
        db.close()


# ---------------------------------------------------------------------------
# The doctor's side: status, re-upload, set password
# ---------------------------------------------------------------------------
PUBLIC_STATUS = {S.CHECKING: "Your documents are being checked.", S.UNDER_REVIEW: "Waiting for review by our team (usually 1-2 working days).",
                 S.NEEDS_INFO: "We need another document from you. Please use the link in our email.",
                 S.APPROVED: "Approved. Use the link in our email to set your password, then sign in.",
                 S.REJECTED: "Not approved. The reason is in our email."}


def status(db: Session, ref: str, email: str) -> dict:
    app = db.get(DoctorApplication, (ref or "").strip().upper())
    if app is None or app.email != (email or "").strip().lower():
        raise AppError(404, "APPLICATION_NOT_FOUND", "No application with this reference and email.")
    return {"reference": app.id, "status": app.status, "message": PUBLIC_STATUS[app.status],
            "submitted_at": app.created_at.isoformat(), "updated_at": app.updated_at.isoformat()}


def reupload_info(db: Session, token: str) -> dict:
    link = _valid_link(db, "REUPLOAD", token)
    app = db.get(DoctorApplication, link.application_id)
    req = json.loads(app.info_request or "{}")
    return {"reference": app.id, "name": app.full_name, "message": req.get("message"),
            "kinds": [{"kind": k, "title": dd.KINDS[k]} for k in req.get("kinds", [])]}


def reupload(db: Session, token: str, files: list[UploadedFile]) -> DoctorApplication:
    link = _valid_link(db, "REUPLOAD", token)
    app = db.get(DoctorApplication, link.application_id)
    if app.status != S.NEEDS_INFO:
        raise AppError(409, "NOT_WAITING", "This application is not waiting for documents.")
    wanted = set(json.loads(app.info_request or "{}").get("kinds", []))
    got = {f.kind for f in files}
    if not wanted <= got:
        raise AppError(422, "DOCUMENTS_MISSING", "Please upload: " + "; ".join(dd.KINDS[k] for k in wanted - got))
    for f in files:
        if f.kind in wanted:
            _store(db, app, f)
    link.used_at = _now()
    app.status, app.info_request = S.CHECKING, None
    db.commit()
    return app


def set_password(db: Session, token: str, password: str) -> User:
    link = _valid_link(db, "SET_PASSWORD", token)
    user = db.get(User, link.user_id)
    if len(password) < 8 or not any(c.isdigit() for c in password) or not any(c.isalpha() for c in password):
        raise AppError(422, "WEAK_PASSWORD", "Use at least 8 characters with letters and numbers.")
    user.password_hash = hash_password(password)
    user.email_verified_at = _now()  # opening the emailed link proves the address; also means "password chosen"
    user.token_version += 1
    link.used_at = _now()
    db.commit()
    return user


def resend_setup_link(db: Session, email: str, origin: str | None = None) -> None:
    """Silent on purpose: the same answer whether or not the email belongs to an approved doctor."""
    user = db.scalar(select(User).where(func.lower(User.email) == (email or "").strip().lower(), User.role == Role.DOCTOR))
    if user is None:
        return
    links = db.scalars(select(OneTimeLink).where(OneTimeLink.user_id == user.id, OneTimeLink.purpose == "SET_PASSWORD")).all()
    # only approved applicants who have not chosen a password yet (set_password marks the email as confirmed)
    if not links or user.email_verified_at is not None:
        return
    if sum(1 for x in links if _aware(x.created_at) > _now() - timedelta(hours=1)) >= MAX_SETUP_LINKS_PER_HOUR:
        return
    token = _new_link(db, "SET_PASSWORD", SET_PASSWORD_TTL, user_id=user.id)
    db.commit()
    doctor_mail.approved(user.email, user.full_name, _link_url("/set-password", token, origin))


# ---------------------------------------------------------------------------
# Admin
# ---------------------------------------------------------------------------
def serialize(db: Session, app: DoctorApplication, *, full: bool = False) -> dict:
    summ = json.loads(app.check_summary) if app.check_summary else None
    out = {"id": app.id, "full_name": app.full_name, "email": app.email, "phone": app.phone,
           "specialization": app.specialization, "qualification": app.qualification,
           "council": {"code": app.council, "name": councils.name(app.council)},
           "registration_number": app.registration_number, "registration_year": app.registration_year,
           "claims_specialist": app.claims_specialist,
           "hospital": ({"id": app.hospital_id, "name": db.get(Hospital, app.hospital_id).name} if app.hospital_id else None),
           "status": app.status, "created_at": app.created_at.isoformat(), "updated_at": app.updated_at.isoformat(),
           "counts": summ["counts"] if summ else None, "decision_note": app.decision_note,
           "info_request": json.loads(app.info_request) if app.info_request else None}
    if full:
        out["checks"] = summ
        out["nmc_register_url"] = councils.NMC_REGISTER_URL
        out["documents"] = [{"id": d.id, "kind": d.kind, "title": dd.KINDS[d.kind], "filename": d.original_filename,
                             "mime_type": d.mime_type, "size_bytes": d.size_bytes, "superseded": d.superseded,
                             "deleted": d.storage_path is None, "read_method": d.read_method,
                             "check": json.loads(d.check_result) if d.check_result else None,
                             "created_at": d.created_at.isoformat()} for d in app.documents]
    return out


def list_applications(db: Session, status_filter: str | None) -> list[DoctorApplication]:
    q = select(DoctorApplication).order_by(DoctorApplication.created_at)
    if status_filter:
        q = q.where(DoctorApplication.status == status_filter)
    return list(db.scalars(q).all())


def get(db: Session, app_id: str) -> DoctorApplication:
    app = db.get(DoctorApplication, app_id)
    if app is None:
        raise AppError(404, "APPLICATION_NOT_FOUND", "Application not found.")
    return app


def _decidable(app: DoctorApplication) -> None:
    if app.status not in (S.UNDER_REVIEW, S.NEEDS_INFO, S.CHECKING):
        raise AppError(409, "ALREADY_DECIDED", f"This application is already {app.status.lower()}.")


def _delete_photo_id(app: DoctorApplication) -> None:
    storage = get_storage()
    for d in app.documents:
        if d.kind == "PHOTO_ID" and d.storage_path:
            if storage.exists(d.storage_path):
                storage.delete(d.storage_path)
            d.storage_path, d.deleted_at = None, _now()


def approve(db: Session, admin: User, app: DoctorApplication, note: str | None, origin: str | None) -> User:
    _decidable(app)
    if app.status == S.CHECKING:
        raise AppError(409, "STILL_CHECKING", "The documents are still being checked. Try again in a minute.")
    if db.scalar(select(User.id).where(func.lower(User.email) == app.email)):
        raise AppError(409, "EMAIL_TAKEN", "An account with this email already exists.")
    if db.scalar(select(Doctor.id).where(func.upper(Doctor.license_number) == app.registration_number.upper())):
        raise AppError(409, "LICENSE_TAKEN", "A doctor with this registration number already exists.")
    # nobody knows this password; the doctor chooses their own through the emailed link
    user = User(email=app.email, password_hash=hash_password(secrets.token_urlsafe(32)), full_name=app.full_name, role=Role.DOCTOR)
    db.add(user)
    db.flush()
    doctor = Doctor(user_id=user.id, specialization=app.specialization, license_number=app.registration_number,
                    hospital_id=app.hospital_id, verification_status=VerificationStatus.VERIFIED)
    db.add(doctor)
    db.flush()
    db.add(DoctorVerification(doctor_id=doctor.id, status=VerificationStatus.VERIFIED, reviewed_by_user_id=admin.id,
                              notes=f"Approved application {app.id}" + (f": {note}" if note else "")))
    app.status, app.user_id, app.decision_note = S.APPROVED, user.id, note
    app.reviewed_by_user_id, app.reviewed_at = admin.id, _now()
    _delete_photo_id(app)
    token = _new_link(db, "SET_PASSWORD", SET_PASSWORD_TTL, user_id=user.id)
    db.commit()
    doctor_mail.approved(user.email, user.full_name, _link_url("/set-password", token, origin))
    return user


def reject(db: Session, admin: User, app: DoctorApplication, reason: str) -> None:
    _decidable(app)
    app.status, app.decision_note = S.REJECTED, reason
    app.reviewed_by_user_id, app.reviewed_at = admin.id, _now()
    _delete_photo_id(app)
    db.execute(update(OneTimeLink).where(OneTimeLink.application_id == app.id, OneTimeLink.used_at.is_(None)).values(used_at=_now()))
    db.commit()
    doctor_mail.rejected(app.email, app.full_name, app.id, reason)


def request_info(db: Session, admin: User, app: DoctorApplication, kinds: list[str], message: str, origin: str | None) -> None:
    _decidable(app)
    if not kinds or any(k not in dd.KINDS for k in kinds):
        raise AppError(422, "INVALID_DOCUMENT_KIND", "Choose which documents the doctor should upload.")
    app.status = S.NEEDS_INFO
    app.info_request = json.dumps({"kinds": kinds, "message": message, "by": "admin"})
    app.reviewed_by_user_id = admin.id
    token = _new_link(db, "REUPLOAD", REUPLOAD_TTL, application_id=app.id)
    db.commit()
    doctor_mail.needs_info(app.email, app.full_name, app.id, [dd.KINDS[k] for k in kinds], message,
                           _link_url("/doctor/reupload", token, origin))


def read_file(app: DoctorApplication, doc_id: int) -> tuple[ApplicationDocument, bytes]:
    d = next((x for x in app.documents if x.id == doc_id), None)
    if d is None:
        raise AppError(404, "DOCUMENT_NOT_FOUND", "Document not found.")
    if d.storage_path is None:
        raise AppError(410, "DOCUMENT_DELETED", "This file was deleted after the decision (photo IDs are not kept).")
    return d, get_storage().read(d.storage_path)
