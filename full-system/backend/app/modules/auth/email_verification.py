"""6-digit email codes: confirming a patient's address at sign-up ("verify") and resetting a forgotten password
("reset"). Codes of one purpose never work for the other.

- The code is random (secrets), valid for 10 minutes, and only a keyed hash of it is stored (HMAC with JWT_SECRET),
  so a database leak does not reveal live codes.
- 5 wrong tries kill a code; a new code can be requested after 60 seconds, at most 5 per hour.
- A new code replaces the older ones.
- The email contains the code only: no health information.
- Email goes out through SMTP (Gmail with an app password). If SMTP is not set up, the code is written to the
  backend log instead, so the app can still be run locally without an email account.
"""

import hashlib
import hmac
import logging
import secrets
import smtplib
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import AppError
from app.models import EmailCode, User

log = logging.getLogger("ddht.email")

CODE_TTL = timedelta(minutes=10)
MAX_TRIES = 5
RESEND_AFTER = timedelta(seconds=60)
MAX_PER_HOUR = 5


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _aware(t: datetime) -> datetime:
    return t if t.tzinfo else t.replace(tzinfo=timezone.utc)


def _hash(user_id: str, code: str) -> str:
    return hmac.new(get_settings().jwt_secret.encode(), f"{user_id}:{code}".encode(), hashlib.sha256).hexdigest()


def email_configured() -> bool:
    s = get_settings()
    return bool(s.smtp_user.strip() and s.smtp_password.strip())


def _send(to: str, name: str, code: str, purpose: str = "verify") -> bool:
    """True if an email was sent. Without SMTP settings the code goes to the backend log (development only)."""
    s = get_settings()
    if not email_configured():
        log.warning("Email is not set up (SMTP_USER / SMTP_PASSWORD). %s code for %s: %s",
                    "Password-reset" if purpose == "reset" else "Sign-up", to, code)
        return False
    msg = EmailMessage()
    reset = purpose == "reset"
    msg["Subject"] = f"Your DDHT {'password reset ' if reset else ''}code: {code}"
    msg["From"] = f"{s.smtp_from_name} <{s.smtp_user.strip()}>"
    msg["To"] = to
    mins = int(CODE_TTL.total_seconds() // 60)
    msg.set_content(
        f"Hello {name},\n\nYour DDHT password reset code is: {code}\n\n"
        f"It expires in {mins} minutes. Type it on the sign-in page, then choose a new password.\n\n"
        "If you did not ask to reset your password, ignore this email: your password stays the same.\n\n"
        "DDHT (university project; fictional demo data only)" if reset else
        f"Hello {name},\n\nYour DDHT verification code is: {code}\n\n"
        f"It expires in {mins} minutes. Type it on the sign-up page to confirm this is your email.\n\n"
        "If you did not create a DDHT account, you can ignore this email.\n\n"
        "DDHT (university project; fictional demo data only)")
    try:
        with smtplib.SMTP(s.smtp_host, s.smtp_port, timeout=15) as smtp:
            smtp.starttls()
            smtp.login(s.smtp_user.strip(), s.smtp_password.strip().replace(" ", ""))
            smtp.send_message(msg)
        return True
    except (smtplib.SMTPException, OSError) as e:
        log.error("Could not send the %s email to %s: %s", purpose, to, type(e).__name__)
        raise AppError(503, "EMAIL_NOT_SENT", "We couldn't send the email just now. Please try again in a minute.")


def needs_verification(user: User) -> bool:
    return user.role.value == "PATIENT" and user.email_verified_at is None


def can_reset(user: User | None) -> bool:
    """Any active account that has chosen its own password. (A doctor applicant who hasn't set one yet uses the
    set-password link from the approval email instead.)"""
    return user is not None and user.is_active and (user.role.value != "DOCTOR" or user.email_verified_at is not None)


def issue(db: Session, user: User, purpose: str = "verify") -> dict:
    """Create and send a new code. Returns {"sent": bool (False = written to the log), "retry_after": seconds}."""
    now = _now()
    mine = (EmailCode.user_id == user.id, EmailCode.purpose == purpose)
    last = db.scalar(select(EmailCode).where(*mine).order_by(EmailCode.created_at.desc()).limit(1))
    if last and now - _aware(last.created_at) < RESEND_AFTER:
        wait = int((RESEND_AFTER - (now - _aware(last.created_at))).total_seconds()) + 1
        raise AppError(429, "CODE_RECENTLY_SENT", f"A code was just sent. You can ask for a new one in {wait} seconds.")
    hour = db.scalar(select(func.count(EmailCode.id)).where(*mine, EmailCode.created_at >= now - timedelta(hours=1))) or 0
    if hour >= MAX_PER_HOUR:
        raise AppError(429, "TOO_MANY_CODES", "Too many codes were requested. Please try again in an hour.")
    code = f"{secrets.randbelow(10**6):06d}"
    db.execute(update(EmailCode).where(*mine, EmailCode.used_at.is_(None)).values(used_at=now))
    db.add(EmailCode(user_id=user.id, purpose=purpose, code_hash=_hash(user.id, code), expires_at=now + CODE_TTL, created_at=now))
    db.commit()
    sent = _send(user.email, user.full_name, code, purpose)
    return {"sent": sent, "retry_after": int(RESEND_AFTER.total_seconds())}


def verify(db: Session, user: User | None, code: str, purpose: str = "verify") -> None:
    """Check the code (and use it up). For "verify" this also marks the email confirmed; a correct "reset" code proves
    the address too. Raises otherwise. The same error is used for an unknown email, so nobody can probe which
    addresses have accounts."""
    bad = AppError(400, "INVALID_CODE", "That code is wrong or has expired. Check the latest email, or ask for a new code.")
    if user is None:
        raise bad
    row = db.scalar(select(EmailCode).where(EmailCode.user_id == user.id, EmailCode.purpose == purpose, EmailCode.used_at.is_(None))
                    .order_by(EmailCode.created_at.desc()).limit(1))
    if row is None or _aware(row.expires_at) < _now() or row.attempts >= MAX_TRIES:
        raise bad
    if not hmac.compare_digest(row.code_hash, _hash(user.id, code.strip())):
        row.attempts += 1
        left = MAX_TRIES - row.attempts
        if left <= 0:
            row.used_at = _now()
        db.commit()
        raise AppError(400, "INVALID_CODE", f"That code is wrong. {left} tries left." if left > 0 else
                       "That code is wrong, and it has now been cancelled. Please ask for a new code.")
    row.used_at = _now()
    if user.email_verified_at is None:
        user.email_verified_at = _now()
    db.commit()
