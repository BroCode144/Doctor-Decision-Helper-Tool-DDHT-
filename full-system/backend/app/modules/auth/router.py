from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Request
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.core.errors import AppError
from app.core.security import create_access_token, hash_password, verify_password
from app.db.session import get_db
from app.models import AccessLog, Doctor, DoctorVerification, Hospital, Patient, Role, User, VerificationStatus
from app.schemas import LoginRequest, RegisterRequest, ResendCodeRequest, ResetPasswordRequest, VerifyEmailRequest
from app.modules.auth import email_verification as ev
from app.shared.audit import Action, Result, audit

router = APIRouter(tags=["auth"])

# Pre-computed hash so that unknown e-mails take as long as wrong passwords.
_DUMMY_HASH = hash_password("timing-equalizer-not-a-real-password-1")


def serialize_me(user: User) -> dict:
    out = {
        "id": user.id,
        "email": user.email,
        "full_name": user.full_name,
        "role": user.role.value,
        "is_active": user.is_active,
        "email_verified": user.email_verified_at is not None,
        "patient_id": None,
        "doctor_id": None,
        "admin_id": None,
    }
    if user.patient:
        out["patient_id"] = user.patient.id
    if user.doctor:
        d = user.doctor
        out["doctor_id"] = d.id
        out["doctor"] = {
            "id": d.id, "specialization": d.specialization, "license_number": d.license_number,
            "verification_status": d.verification_status.value,
            "hospital": {"id": d.hospital.id, "name": d.hospital.name} if d.hospital else None,
        }
    if user.admin:
        out["admin_id"] = user.admin.id
        out["admin"] = {"id": user.admin.id, "can_manage_patient_documents": user.admin.can_manage_patient_documents}
    return out


LOGIN_WINDOW = timedelta(minutes=15)
MAX_FAILURES_PER_EMAIL = 10
MAX_FAILURES_PER_IP = 30


def _check_login_rate_limit(db: Session, email: str, ip: str | None) -> None:
    """Brute-force protection based on recent LOGIN_FAILURE audit rows."""
    since = datetime.now(timezone.utc) - LOGIN_WINDOW
    recent = select(func.count(AccessLog.id)).where(AccessLog.action == Action.LOGIN_FAILURE, AccessLog.timestamp >= since)
    by_email = db.scalar(recent.where(func.lower(AccessLog.user_email) == email)) or 0
    # Traffic arriving through the Cloudflare tunnel appears to come from this laptop (loopback).
    # Counting it per IP would let one person lock out every public visitor, so only the
    # per-email limit applies to it.
    local = ip is None or ip in ("127.0.0.1", "::1", "::ffff:127.0.0.1", "testclient")
    by_ip = 0 if local else (db.scalar(recent.where(AccessLog.ip_address == ip)) or 0)
    if by_email >= MAX_FAILURES_PER_EMAIL or by_ip >= MAX_FAILURES_PER_IP:
        raise AppError(429, "TOO_MANY_ATTEMPTS",
                       "Too many failed sign-in attempts. Please wait 15 minutes and try again.")


@router.post("/auth/login")
def login(body: LoginRequest, request: Request, db: Session = Depends(get_db)):
    email = body.email.lower()
    _check_login_rate_limit(db, email, request.client.host if request.client else None)
    user = db.scalar(select(User).where(func.lower(User.email) == email))
    if user is None:
        verify_password(body.password, _DUMMY_HASH)
        audit(Action.LOGIN_FAILURE, Result.FAILURE, user_email=email, reason="Unknown email", request=request)
        raise AppError(401, "INVALID_CREDENTIALS", "Invalid email or password.")
    if not verify_password(body.password, user.password_hash):
        audit(Action.LOGIN_FAILURE, Result.FAILURE, user=user, reason="Wrong password", request=request)
        raise AppError(401, "INVALID_CREDENTIALS", "Invalid email or password.")
    if not user.is_active:
        audit(Action.LOGIN_FAILURE, Result.DENIED, user=user, reason="Account inactive", request=request)
        raise AppError(403, "ACCOUNT_INACTIVE", "This account has been deactivated. Contact an administrator.")
    if ev.needs_verification(user):
        # The password was right, so it is safe to say the email is unconfirmed and send a fresh code.
        try:
            sent = ev.issue(db, user)["sent"]
            audit(Action.EMAIL_CODE_SENT, Result.SUCCESS, user=user, reason="sign-in before confirming email", request=request)
        except AppError as e:
            if e.code not in ("CODE_RECENTLY_SENT", "TOO_MANY_CODES"):
                raise
            sent = None  # the last code is still valid
        raise AppError(403, "EMAIL_NOT_VERIFIED", "Please confirm your email first: type the 6-digit code we emailed you.",
                       email=user.email, email_sent=sent)
    user.last_login_at = datetime.now(timezone.utc)
    db.commit()
    audit(Action.LOGIN_SUCCESS, Result.SUCCESS, user=user, request=request)
    token = create_access_token(user.id, user.role.value, user.token_version)
    return {"access_token": token, "token_type": "bearer", "user": serialize_me(user)}


@router.post("/auth/logout")
def logout(request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    user = db.merge(user)
    user.token_version += 1  # invalidates every token issued so far
    db.commit()
    audit(Action.LOGOUT, Result.SUCCESS, user=user, request=request)
    return {"message": "Logged out."}


@router.post("/auth/register", status_code=201)
def register(body: RegisterRequest, request: Request, db: Session = Depends(get_db)):
    email = body.email.lower()
    if db.scalar(select(User).where(func.lower(User.email) == email)):
        raise AppError(409, "EMAIL_TAKEN", "An account with this email already exists.")
    role = Role(body.role)
    if role == Role.DOCTOR:  # doctors apply with documents instead (app/modules/doctors/router.py)
        raise AppError(422, "DOCTORS_MUST_APPLY", "Doctors join through the doctor application with their registration documents.")
    license_number = (body.license_number or "").strip()
    if role == Role.DOCTOR:
        # Validate everything before writing anything.
        if not (body.specialization or "").strip() or not license_number:
            raise AppError(422, "DOCTOR_FIELDS_REQUIRED", "Specialization and license number are required for doctors.")
        if body.hospital_id and db.get(Hospital, body.hospital_id) is None:
            raise AppError(422, "INVALID_HOSPITAL", "Unknown hospital.")
        if db.scalar(select(Doctor).where(func.lower(Doctor.license_number) == license_number.lower())):
            raise AppError(409, "LICENSE_TAKEN", "A doctor with this license number is already registered.")
    try:
        user = User(email=email, password_hash=hash_password(body.password), full_name=body.full_name.strip(), role=role)
        db.add(user)
        db.flush()
        if role == Role.PATIENT:
            db.add(Patient(user_id=user.id, date_of_birth=body.date_of_birth, gender=body.gender, phone=body.phone))
        else:
            doctor = Doctor(user_id=user.id, specialization=body.specialization.strip(), license_number=license_number,
                            hospital_id=body.hospital_id, verification_status=VerificationStatus.PENDING)
            db.add(doctor)
            db.flush()
            db.add(DoctorVerification(doctor_id=doctor.id, status=VerificationStatus.PENDING, notes="Self-registered"))
        db.commit()
    except IntegrityError:
        # Two sign-ups racing for the same email / license number.
        db.rollback()
        raise AppError(409, "DUPLICATE", "An account with these details already exists (email or license number).")
    db.refresh(user)
    audit(Action.USER_REGISTERED, Result.SUCCESS, user=user, reason=f"role={role.value}", request=request)
    if ev.needs_verification(user):
        sent = ev.issue(db, user)["sent"]
        audit(Action.EMAIL_CODE_SENT, Result.SUCCESS, user=user, reason="sign-up", request=request)
        return {"user": serialize_me(user), "needs_verification": True, "email": user.email, "email_sent": sent,
                "message": "Account created. We've emailed you a 6-digit code to confirm your email."}
    return {"user": serialize_me(user), "needs_verification": False,
            "message": "Registration successful." + (" A doctor account must be verified by an administrator before it can access patient records." if role == Role.DOCTOR else "")}


@router.post("/auth/verify-email")
def verify_email(body: VerifyEmailRequest, request: Request, db: Session = Depends(get_db)):
    """The code from the sign-up email. On success the patient is signed in."""
    email = body.email.lower()
    user = db.scalar(select(User).where(func.lower(User.email) == email))
    if user is not None and not ev.needs_verification(user):
        raise AppError(409, "ALREADY_VERIFIED", "This email is already confirmed. Please sign in.")
    try:
        ev.verify(db, user, body.code)
    except AppError:
        audit(Action.EMAIL_CODE_FAILED, Result.FAILURE, user=user, user_email=email, reason="wrong or expired code", request=request)
        raise
    if not user.is_active:
        raise AppError(403, "ACCOUNT_INACTIVE", "This account has been deactivated. Contact an administrator.")
    user.last_login_at = datetime.now(timezone.utc)
    db.commit()
    audit(Action.EMAIL_VERIFIED, Result.SUCCESS, user=user, request=request)
    audit(Action.LOGIN_SUCCESS, Result.SUCCESS, user=user, reason="after confirming email", request=request)
    token = create_access_token(user.id, user.role.value, user.token_version)
    return {"access_token": token, "token_type": "bearer", "user": serialize_me(user)}


@router.post("/auth/resend-code")
def resend_code(body: ResendCodeRequest, request: Request, db: Session = Depends(get_db)):
    """Always the same answer, so nobody can use it to find out which emails have accounts."""
    user = db.scalar(select(User).where(func.lower(User.email) == body.email.lower()))
    sent = None
    if user is not None and ev.needs_verification(user):
        try:
            sent = ev.issue(db, user)["sent"]
            audit(Action.EMAIL_CODE_SENT, Result.SUCCESS, user=user, reason="resend", request=request)
        except AppError as e:  # too soon / too many: answer the same way (the page has its own 60-second timer)
            if e.code not in ("CODE_RECENTLY_SENT", "TOO_MANY_CODES"):
                raise
    return {"message": "If this email has an account waiting for confirmation, a new code is on its way.",
            "email_sent": sent if sent is not None else ev.email_configured()}


@router.post("/auth/forgot-password")
def forgot_password(body: ResendCodeRequest, request: Request, db: Session = Depends(get_db)):
    """Email a 6-digit reset code. Always the same answer, so nobody can find out which emails have accounts."""
    user = db.scalar(select(User).where(func.lower(User.email) == body.email.lower()))
    if ev.can_reset(user):
        try:
            ev.issue(db, user, "reset")
            audit(Action.PASSWORD_RESET_REQUESTED, Result.SUCCESS, user=user, request=request)
        except AppError as e:  # too soon / too many: answer the same way (the page has its own 60-second timer)
            if e.code not in ("CODE_RECENTLY_SENT", "TOO_MANY_CODES"):
                raise
    return {"message": "If this email has a DDHT account, we've sent a code to it. It expires in 10 minutes.",
            "email_sent": ev.email_configured()}


@router.post("/auth/reset-password")
def reset_password(body: ResetPasswordRequest, request: Request, db: Session = Depends(get_db)):
    """The emailed code plus a new password. Signs the account out everywhere; the user then signs in again."""
    email = body.email.lower()
    user = db.scalar(select(User).where(func.lower(User.email) == email))
    try:
        ev.verify(db, user if ev.can_reset(user) else None, body.code, "reset")
    except AppError:
        audit(Action.PASSWORD_RESET_FAILED, Result.FAILURE, user=user, user_email=email, reason="wrong or expired code",
              request=request)
        raise
    user.password_hash = hash_password(body.password)
    user.token_version += 1  # every old session ends
    db.commit()
    audit(Action.PASSWORD_RESET, Result.SUCCESS, user=user, request=request)
    return {"message": "Your password has been changed. Please sign in with the new password."}


@router.get("/users/me")
def me(user: User = Depends(get_current_user)):
    return serialize_me(user)
