"""Emails to doctors about their application. Same Gmail settings as the sign-up codes (SMTP_USER / SMTP_PASSWORD).

If Gmail is not set up, each email is saved as a .txt file in storage/outbox/ (OUTBOX_DIR) instead, so the flow can
be shown in a demo without sending anything. Emails never contain medical information, documents or passwords:
only the status, the reason, and one-time links.
"""

import logging
import re
import smtplib
from datetime import datetime, timezone
from email.message import EmailMessage

from app.core.config import get_settings
from app.modules.auth.email_verification import email_configured

log = logging.getLogger("ddht.email")
FOOTER = "\n\nDDHT (university project; fictional demo data only)"


def _hello(name: str) -> str:
    """'Hello Dr. X' even when the applicant already typed 'Dr.' in their name."""
    bare = re.sub(r"^\s*dr\.?\s+", "", name, flags=re.I)
    return f"Hello Dr. {bare}"


def send(to: str, subject: str, body: str) -> str:
    """'sent' (Gmail), 'outbox' (saved to a file) or 'failed'. Never raises: the decision is already saved."""
    s = get_settings()
    if not email_configured():
        try:
            s.outbox_dir.mkdir(parents=True, exist_ok=True)
            stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S-%f")
            (s.outbox_dir / f"{stamp}.txt").write_text(f"To: {to}\nSubject: {subject}\n\n{body}{FOOTER}\n", encoding="utf-8")
            return "outbox"
        except OSError:
            log.error("Could not save an email to the outbox")
            return "failed"
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = f"{s.smtp_from_name} <{s.smtp_user.strip()}>"
    msg["To"] = to
    msg.set_content(body + FOOTER)
    try:
        with smtplib.SMTP(s.smtp_host, s.smtp_port, timeout=15) as smtp:
            smtp.starttls()
            smtp.login(s.smtp_user.strip(), s.smtp_password.strip().replace(" ", ""))
            smtp.send_message(msg)
        return "sent"
    except (smtplib.SMTPException, OSError) as e:
        log.error("Could not send email to %s: %s", to, type(e).__name__)
        return "failed"


def received(to: str, name: str, ref: str) -> str:
    return send(to, f"DDHT: application {ref} received",
                f"{_hello(name)},\n\nWe received your application to join DDHT as a doctor. Your reference is {ref}.\n\n"
                "Your documents are checked automatically first, then by our team. This usually takes 1-2 working days. "
                "We will email you when there is news. You can also check the status any time on the 'Check application "
                "status' page with your reference and email.")


def needs_info(to: str, name: str, ref: str, items: list[str], message: str | None, link: str) -> str:
    lines = "\n".join(f"  - {i}" for i in items)
    return send(to, f"DDHT: application {ref} needs another document",
                f"{_hello(name)},\n\nTo continue with application {ref}, please upload:\n{lines}\n\n"
                + (f"Note from our team: {message}\n\n" if message else "")
                + f"Upload here (link valid for 7 days, works once):\n{link}")


def approved(to: str, name: str, link: str) -> str:
    return send(to, "DDHT: you're approved, set your password",
                f"{_hello(name)},\n\nYour DDHT doctor account has been approved.\n\nChoose your password here "
                f"(link valid for 48 hours, works once):\n{link}\n\nThen sign in with this email address. "
                "If the link has expired, use 'Send a new link' on that page.")


def rejected(to: str, name: str, ref: str, reason: str) -> str:
    return send(to, f"DDHT: application {ref} was not approved",
                f"{_hello(name)},\n\nWe could not approve application {ref}.\n\nReason: {reason}\n\n"
                "If you think this is a mistake, you can apply again with the correct documents.")
