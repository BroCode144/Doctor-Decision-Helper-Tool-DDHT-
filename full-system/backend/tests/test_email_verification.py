"""Patients confirm their email with a 6-digit code at sign-up; they cannot sign in before that."""

from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models import EmailCode, User
from tests.conftest import SENT_CODES, login, logs

NEW = {"email": "Asha.Patel@example.com", "password": "patient2026", "full_name": "Asha Patel", "role": "PATIENT"}
EMAIL = NEW["email"].lower()


def _age_codes(seconds):
    """Pretend the codes were sent `seconds` ago (to get past the 60-second resend wait or the 10-minute expiry)."""
    with SessionLocal() as db:
        for c in db.scalars(select(EmailCode)):
            c.created_at -= timedelta(seconds=seconds)
            c.expires_at -= timedelta(seconds=seconds)
        db.commit()


def _verify(client, code, email=EMAIL):
    return client.post("/auth/verify-email", json={"email": email, "code": code})


def test_sign_up_sends_a_code_and_sign_in_waits_for_it(client, admin):
    r = client.post("/auth/register", json=NEW)
    assert r.status_code == 201 and r.json()["needs_verification"] and EMAIL in SENT_CODES
    code = SENT_CODES[EMAIL]
    assert len(code) == 6 and code.isdigit()
    # the password alone does not get in
    r = client.post("/auth/login", json={"email": EMAIL, "password": NEW["password"]})
    assert r.status_code == 403 and r.json()["detail"]["code"] == "EMAIL_NOT_VERIFIED"
    assert r.json()["detail"]["email_sent"] is None  # the code from a moment ago is still valid; no new email
    # the code signs the patient in, once
    r = _verify(client, code)
    assert r.status_code == 200 and r.json()["user"]["email_verified"] and r.json()["access_token"]
    assert _verify(client, code).json()["detail"]["code"] == "ALREADY_VERIFIED"
    assert login(client, EMAIL, NEW["password"])
    assert logs(client, admin, action="EMAIL_VERIFIED")
    # only a hash is stored
    with SessionLocal() as db:
        assert all(code not in c.code_hash for c in db.scalars(select(EmailCode)))


def test_wrong_codes_are_limited(client):
    client.post("/auth/register", json=NEW)
    good = SENT_CODES[EMAIL]
    wrong = "000000" if good != "000000" else "111111"
    for left in (4, 3, 2, 1):
        r = _verify(client, wrong)
        assert r.status_code == 400 and f"{left} tries left" in r.json()["detail"]["message"]
    assert "cancelled" in _verify(client, wrong).json()["detail"]["message"]
    assert _verify(client, good).status_code == 400  # the right code no longer works after 5 wrong tries
    # a new code (after the 60-second wait) works
    _age_codes(61)
    assert client.post("/auth/resend-code", json={"email": EMAIL}).status_code == 200
    assert SENT_CODES[EMAIL] and _verify(client, SENT_CODES[EMAIL]).status_code == 200


def test_codes_expire_and_resend_rules(client):
    client.post("/auth/register", json=NEW)
    first = SENT_CODES[EMAIL]
    # asking again straight away sends nothing new (same polite answer)
    r = client.post("/auth/resend-code", json={"email": EMAIL})
    assert r.status_code == 200 and SENT_CODES[EMAIL] == first
    _age_codes(11 * 60)  # past the 10-minute expiry
    assert _verify(client, first).status_code == 400
    client.post("/auth/resend-code", json={"email": EMAIL})
    second = SENT_CODES[EMAIL]
    assert second  # a new code replaces the old one
    if second != first:
        _age_codes(61)
        client.post("/auth/resend-code", json={"email": EMAIL})
        assert _verify(client, second).status_code == 400  # older codes stop working once a newer one is sent


def test_nothing_reveals_which_emails_have_accounts(client):
    a = client.post("/auth/resend-code", json={"email": "nobody@example.com"})
    b = client.post("/auth/resend-code", json={"email": "patient@ddht.demo"})  # exists, already confirmed
    assert a.status_code == b.status_code == 200 and a.json()["message"] == b.json()["message"]
    r = _verify(client, "123456", email="nobody@example.com")
    assert r.status_code == 400 and r.json()["detail"]["code"] == "INVALID_CODE"
    # a wrong password never says "not confirmed"
    client.post("/auth/register", json=NEW)
    assert client.post("/auth/login", json={"email": EMAIL, "password": "wrong-pass1"}).json()["detail"]["code"] == "INVALID_CREDENTIALS"


def test_doctors_and_existing_accounts_are_not_asked(client):
    r = client.post("/auth/register", json={"email": "dr.new@example.com", "password": "doctor2026", "full_name": "Dr New",
                                            "role": "DOCTOR", "specialization": "ENT", "license_number": "LIC-EV-1"})
    # doctors apply with documents instead and confirm their email through the set-password link
    assert r.status_code == 422 and "dr.new@example.com" not in SENT_CODES
    assert login(client, "patient@ddht.demo", "patient123")  # seeded accounts count as confirmed
    with SessionLocal() as db:
        assert db.scalar(select(User).where(User.email == "patient@ddht.demo")).email_verified_at <= datetime.now(timezone.utc)
