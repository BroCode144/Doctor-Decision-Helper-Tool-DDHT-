"""Doctor applications: public endpoints for the doctor, admin endpoints for the review queue.

Public (no account yet): apply, check status, re-upload (one-time link), set password (one-time link), new link.
Admin: list, view (with the automatic checklist), open a file (audited), approve / ask for more / reject.
"""

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, Request, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import Response
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.deps import require_roles
from app.core.config import get_settings
from app.core.errors import AppError
from app.db.session import get_db
from app.models import Hospital, Role, User
from app.models.doctor_onboarding import ApplicationStatus
from app.modules.doctors import councils
from app.modules.doctors import doctor_documents as dd
from app.modules.doctors import doctor_onboarding as svc
from app.shared.audit import Result, audit

router = APIRouter(tags=["doctor-applications"])
admin_only = require_roles(Role.ADMIN)


class Act:
    SUBMITTED = "DOCTOR_APPLICATION_SUBMITTED"
    REUPLOADED = "DOCTOR_APPLICATION_REUPLOADED"
    VIEWED = "DOCTOR_APPLICATION_VIEWED"
    FILE_OPENED = "DOCTOR_APPLICATION_FILE_OPENED"
    APPROVED = "DOCTOR_APPLICATION_APPROVED"
    REJECTED = "DOCTOR_APPLICATION_REJECTED"
    INFO_REQUESTED = "DOCTOR_APPLICATION_INFO_REQUESTED"
    PASSWORD_SET = "DOCTOR_PASSWORD_SET"


async def _files(pairs: list[tuple[str, UploadFile | None]]) -> list[svc.UploadedFile]:
    limit = get_settings().max_upload_bytes
    out = []
    for kind, f in pairs:
        if f is not None and f.filename:
            out.append(svc.UploadedFile(kind, f.filename, f.content_type, await f.read(limit + 1)))
    return out


def _origin(request: Request) -> str | None:
    """Links in admin-triggered emails point back to the site the admin is using (the admin is signed in)."""
    return request.headers.get("origin")


# ---------------------------------------------------------------------------
# Public
# ---------------------------------------------------------------------------
@router.get("/doctor-applications/options")
def options(db: Session = Depends(get_db)):
    return {"councils": councils.options(), "documents": [{"kind": k, "title": t} for k, t in dd.KINDS.items()],
            "hospitals": [{"id": h.id, "name": h.name} for h in db.scalars(select(Hospital).order_by(Hospital.name))]}


@router.post("/doctor-applications", status_code=201)
async def apply(
    request: Request,
    background: BackgroundTasks,
    full_name: str = Form(..., min_length=2, max_length=200),
    email: EmailStr = Form(...),
    phone: str | None = Form(None, max_length=32),
    specialization: str = Form(..., min_length=2, max_length=120),
    qualification: str = Form(..., min_length=2, max_length=120),
    council: str = Form(..., max_length=16),
    registration_number: str = Form(..., min_length=3, max_length=40, pattern=r"^[A-Za-z0-9/\- ]+$"),
    registration_year: int = Form(...),
    claims_specialist: bool = Form(False),
    hospital_id: str | None = Form(None),
    registration_certificate: UploadFile | None = File(None),
    degree_certificate: UploadFile | None = File(None),
    photo_id: UploadFile | None = File(None),
    pg_degree: UploadFile | None = File(None),
    hospital_letter: UploadFile | None = File(None),
    db: Session = Depends(get_db),
):
    files = await _files([("REGISTRATION", registration_certificate), ("DEGREE", degree_certificate), ("PHOTO_ID", photo_id),
                          ("PG_DEGREE", pg_degree), ("HOSPITAL_LETTER", hospital_letter)])
    fields = {"full_name": full_name, "email": str(email), "phone": (phone or "").strip() or None,
              "specialization": specialization.strip(), "qualification": qualification.strip(), "council": council,
              "registration_number": registration_number, "registration_year": registration_year,
              "claims_specialist": claims_specialist, "hospital_id": hospital_id or None}
    app = await run_in_threadpool(svc.submit, db, fields, files)
    audit(Act.SUBMITTED, Result.SUCCESS, user_email=app.email, resource_type="doctor_application", resource_id=app.id, request=request)
    background.add_task(svc.run_checks, app.id)
    return {"reference": app.id, "status": app.status,
            "message": f"Application {app.id} received. We've emailed you; you'll hear from us within 1-2 working days."}


@router.get("/doctor-applications/status")
def status(reference: str, email: str, db: Session = Depends(get_db)):
    return svc.status(db, reference, email)


class TokenBody(BaseModel):
    token: str = Field(min_length=10, max_length=200)


@router.post("/doctor-applications/reupload/info")
def reupload_info(body: TokenBody, db: Session = Depends(get_db)):
    return svc.reupload_info(db, body.token)


@router.post("/doctor-applications/reupload")
async def reupload(
    request: Request,
    background: BackgroundTasks,
    token: str = Form(..., min_length=10, max_length=200),
    registration_certificate: UploadFile | None = File(None),
    degree_certificate: UploadFile | None = File(None),
    photo_id: UploadFile | None = File(None),
    pg_degree: UploadFile | None = File(None),
    hospital_letter: UploadFile | None = File(None),
    db: Session = Depends(get_db),
):
    files = await _files([("REGISTRATION", registration_certificate), ("DEGREE", degree_certificate), ("PHOTO_ID", photo_id),
                          ("PG_DEGREE", pg_degree), ("HOSPITAL_LETTER", hospital_letter)])
    app = await run_in_threadpool(svc.reupload, db, token, files)
    audit(Act.REUPLOADED, Result.SUCCESS, user_email=app.email, resource_type="doctor_application", resource_id=app.id, request=request)
    background.add_task(svc.run_checks, app.id)
    return {"reference": app.id, "status": app.status, "message": "Thank you. Your new documents are being checked."}


class SetPasswordBody(TokenBody):
    password: str = Field(min_length=8, max_length=200)


@router.post("/auth/set-password")
def set_password(body: SetPasswordBody, request: Request, db: Session = Depends(get_db)):
    user = svc.set_password(db, body.token, body.password)
    audit(Act.PASSWORD_SET, Result.SUCCESS, user=user, request=request)
    return {"email": user.email, "message": "Password saved. You can sign in now."}


class EmailBody(BaseModel):
    email: EmailStr


@router.post("/auth/set-password/new-link")
def new_setup_link(body: EmailBody, request: Request, db: Session = Depends(get_db)):
    svc.resend_setup_link(db, str(body.email), _origin(request))
    return {"message": "If this email belongs to an approved doctor who hasn't set a password yet, we've sent a new link."}


# ---------------------------------------------------------------------------
# Admin
# ---------------------------------------------------------------------------
@router.get("/admin/doctor-applications")
def admin_list(status: str | None = None, _: User = Depends(admin_only), db: Session = Depends(get_db)):
    if status and status not in ApplicationStatus.ALL:
        raise AppError(422, "INVALID_STATUS", "Invalid status.")
    return [svc.serialize(db, a) for a in svc.list_applications(db, status)]


@router.get("/admin/doctor-applications/{app_id}")
def admin_get(app_id: str, request: Request, admin: User = Depends(admin_only), db: Session = Depends(get_db)):
    app = svc.get(db, app_id)
    audit(Act.VIEWED, Result.SUCCESS, user=admin, resource_type="doctor_application", resource_id=app.id, request=request)
    return svc.serialize(db, app, full=True)


@router.get("/admin/doctor-applications/{app_id}/documents/{doc_id}")
def admin_file(app_id: str, doc_id: int, request: Request, admin: User = Depends(admin_only), db: Session = Depends(get_db)):
    app = svc.get(db, app_id)
    d, data = svc.read_file(app, doc_id)
    audit(Act.FILE_OPENED, Result.SUCCESS, user=admin, resource_type="doctor_application", resource_id=app.id,
          reason=f"{d.kind} (document {d.id})", request=request)
    return Response(content=data, media_type=d.mime_type, headers={"Content-Disposition": "inline", "Cache-Control": "no-store"})


class DecisionBody(BaseModel):
    note: str | None = Field(None, max_length=1000)


class RejectBody(BaseModel):
    reason: str = Field(min_length=5, max_length=1000)


class InfoBody(BaseModel):
    kinds: list[str] = Field(min_length=1, max_length=5)
    message: str = Field(min_length=5, max_length=1000)


@router.post("/admin/doctor-applications/{app_id}/approve")
def admin_approve(app_id: str, request: Request, body: DecisionBody | None = None, admin: User = Depends(admin_only), db: Session = Depends(get_db)):
    app = svc.get(db, app_id)
    user = svc.approve(db, admin, app, body.note if body else None, _origin(request))
    audit(Act.APPROVED, Result.SUCCESS, user=admin, resource_type="doctor_application", resource_id=app.id,
          reason=f"doctor account {user.doctor.id if user.doctor else user.id}", request=request)
    return svc.serialize(db, app)


@router.post("/admin/doctor-applications/{app_id}/reject")
def admin_reject(app_id: str, body: RejectBody, request: Request, admin: User = Depends(admin_only), db: Session = Depends(get_db)):
    app = svc.get(db, app_id)
    svc.reject(db, admin, app, body.reason.strip())
    audit(Act.REJECTED, Result.SUCCESS, user=admin, resource_type="doctor_application", resource_id=app.id, reason=body.reason[:200], request=request)
    return svc.serialize(db, app)


@router.post("/admin/doctor-applications/{app_id}/request-info")
def admin_request_info(app_id: str, body: InfoBody, request: Request, admin: User = Depends(admin_only), db: Session = Depends(get_db)):
    app = svc.get(db, app_id)
    svc.request_info(db, admin, app, body.kinds, body.message.strip(), _origin(request))
    audit(Act.INFO_REQUESTED, Result.SUCCESS, user=admin, resource_type="doctor_application", resource_id=app.id,
          reason=", ".join(body.kinds), request=request)
    return svc.serialize(db, app)

