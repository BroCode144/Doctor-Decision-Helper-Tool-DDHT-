"""Forgot password: a 6-digit code goes to the account's email; with it the user chooses a new password."""

from tests.conftest import SENT_CODES, logs

EMAIL = "patient@ddht.demo"


def _forgot(client, email=EMAIL):
    r = client.post("/auth/forgot-password", json={"email": email})
    assert r.status_code == 200
    return r.json()


def _reset(client, code, password="newpass2026", email=EMAIL):
    return client.post("/auth/reset-password", json={"email": email, "code": code, "password": password})


def test_reset_with_the_emailed_code(client, admin):
    old = client.post("/auth/login", json={"email": EMAIL, "password": "patient123"}).json()["access_token"]
    _forgot(client)
    code = SENT_CODES[EMAIL]
    assert _reset(client, code).status_code == 200
    # new password works, old one doesn't, old sessions are signed out, the code can't be reused
    assert client.post("/auth/login", json={"email": EMAIL, "password": "newpass2026"}).status_code == 200
    assert client.post("/auth/login", json={"email": EMAIL, "password": "patient123"}).status_code == 401
    assert client.get("/users/me", headers={"Authorization": f"Bearer {old}"}).status_code == 401
    assert _reset(client, code, "another2026").status_code == 400
    assert logs(client, admin, action="PASSWORD_RESET")


def test_wrong_codes_and_weak_passwords(client):
    _forgot(client)
    good = SENT_CODES[EMAIL]
    assert _reset(client, good, "short1").status_code == 422
    assert _reset(client, good, "lettersonly").status_code == 422
    wrong = "000000" if good != "000000" else "111111"
    r = _reset(client, wrong)
    assert r.status_code == 400 and "4 tries left" in r.json()["detail"]["message"]
    assert _reset(client, good).status_code == 200  # still valid after one wrong try


def test_codes_do_not_cross_purposes_and_nothing_leaks(client):
    a, b = _forgot(client, "nobody@example.com"), _forgot(client)
    assert a["message"] == b["message"] and "nobody@example.com" not in SENT_CODES
    assert _reset(client, "123456", email="nobody@example.com").status_code == 400
    # a reset code is not a sign-up code
    r = client.post("/auth/verify-email", json={"email": EMAIL, "code": SENT_CODES[EMAIL]})
    assert r.status_code in (400, 409)
    # asking again straight away sends nothing new
    first = SENT_CODES[EMAIL]
    _forgot(client)
    assert SENT_CODES[EMAIL] == first


def test_works_for_staff_too(client):
    _forgot(client, "doctor@ddht.demo")
    assert _reset(client, SENT_CODES["doctor@ddht.demo"], "doctor2027x", "doctor@ddht.demo").status_code == 200
    assert client.post("/auth/login", json={"email": "doctor@ddht.demo", "password": "doctor2027x"}).status_code == 200
