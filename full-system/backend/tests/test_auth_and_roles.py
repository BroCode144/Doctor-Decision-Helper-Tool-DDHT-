"""1-4: login success/failure, JWT, role authorization (+ logout, registration)."""

import jwt

from tests.conftest import login, logs, register


def test_login_success_returns_jwt_and_profile(client):
    r = client.post("/auth/login", json={"email": "doctor@ddht.demo", "password": "doctor123"})
    assert r.status_code == 200
    body = r.json()
    assert body["token_type"] == "bearer"
    assert body["user"]["role"] == "DOCTOR" and body["user"]["doctor_id"] == "D001"
    assert "password" not in str(body).lower().replace("password_", "")


def test_login_failure_wrong_password_and_unknown_user(client, admin):
    r = client.post("/auth/login", json={"email": "doctor@ddht.demo", "password": "wrong"})
    assert r.status_code == 401
    assert r.json()["detail"]["message"] == "Invalid email or password."
    r2 = client.post("/auth/login", json={"email": "nobody@ddht.demo", "password": "x"})
    assert r2.status_code == 401
    fails = logs(client, admin, action="LOGIN_FAILURE")
    assert len(fails) >= 2


def test_login_success_is_logged(client, admin):
    login(client, "patient@ddht.demo", "patient123")
    assert any(l["user_email"] == "patient@ddht.demo" for l in logs(client, admin, action="LOGIN_SUCCESS"))


def test_jwt_required_and_validated(client, doctor):
    assert client.get("/users/me").status_code == 401
    assert client.get("/users/me", headers={"Authorization": "Bearer not-a-jwt"}).status_code == 401
    forged = jwt.encode({"sub": "x", "role": "ADMIN", "tv": 0, "exp": 9999999999}, "wrong-secret-" + "y" * 40, algorithm="HS256")
    assert client.get("/users/me", headers={"Authorization": f"Bearer {forged}"}).status_code == 401
    r = client.get("/users/me", headers=doctor)
    assert r.status_code == 200 and r.json()["email"] == "doctor@ddht.demo"


def test_logout_invalidates_token(client, doctor):
    assert client.post("/auth/logout", headers=doctor).status_code == 200
    assert client.get("/users/me", headers=doctor).status_code == 401


def test_role_authorization(client, doctor, patient, admin):
    assert client.get("/admin/users", headers=doctor).status_code == 403
    assert client.get("/admin/users", headers=patient).status_code == 403
    assert client.get("/admin/users", headers=admin).status_code == 200
    # consent management is patient-only
    assert client.post("/patients/P001/consent/D002", headers=doctor).status_code == 403
    # AI is doctor-only
    assert client.post("/ai/patients/P001/ask", headers=patient, json={"question": "What diagnoses?"}).status_code == 403
    assert client.post("/ai/patients/P001/ask", headers=admin, json={"question": "What diagnoses?"}).status_code == 403


def test_passwords_are_hashed(client):
    from sqlalchemy import select

    from app.db.session import SessionLocal
    from app.models import User

    with SessionLocal() as db:
        for u in db.scalars(select(User)):
            assert u.password_hash.startswith("$2") and "123" not in u.password_hash


def test_register_patient_and_pending_doctor(client, admin):
    r = register(client, {"email": "new.patient@ddht.demo", "password": "secret123",
                                            "full_name": "New Patient", "role": "PATIENT"})
    assert r.status_code == 201
    h = login(client, "new.patient@ddht.demo", "secret123")
    assert client.get("/users/me", headers=h).json()["patient_id"]
    r = client.post("/auth/register", json={"email": "new.doc@ddht.demo", "password": "secret123", "full_name": "Dr. New",
                                            "role": "DOCTOR", "specialization": "ENT", "license_number": "LIC-NEW-1"})
    # doctors now apply with documents (tests/test_doctor_applications.py); direct sign-up is refused
    assert r.status_code == 422 and r.json()["detail"]["code"] == "DOCTORS_MUST_APPLY"
    # cannot self-register as admin
    r = client.post("/auth/register", json={"email": "evil@ddht.demo", "password": "secret123", "full_name": "Evil", "role": "ADMIN"})
    assert r.status_code == 422


def test_inactive_user_cannot_login(client, admin):
    users = client.get("/admin/users", headers=admin, params={"q": "priya"}).json()
    uid = users[0]["id"]
    assert client.patch(f"/admin/users/{uid}/status", headers=admin, json={"is_active": False}).status_code == 200
    r = client.post("/auth/login", json={"email": "priya@ddht.demo", "password": "patient123"})
    assert r.status_code == 403


def test_login_rate_limit_after_repeated_failures(client, admin):
    for _ in range(10):
        assert client.post("/auth/login", json={"email": "priya@ddht.demo", "password": "wrong"}).status_code == 401
    # Even the correct password is refused while locked out.
    r = client.post("/auth/login", json={"email": "priya@ddht.demo", "password": "patient123"})
    assert r.status_code == 429 and r.json()["detail"]["code"] == "TOO_MANY_ATTEMPTS"
    # Other accounts are unaffected.
    assert client.post("/auth/login", json={"email": "aman@ddht.demo", "password": "patient123"}).status_code == 200


def test_login_failures_from_the_tunnel_do_not_lock_out_everyone(client):
    # All test requests share one client address, like tunnel traffic. 35 failures spread
    # over several emails must not block a different user's correct login.
    for i in range(35):
        client.post("/auth/login", json={"email": f"nobody{i % 5}@ddht.demo", "password": "x"})
    assert client.post("/auth/login", json={"email": "doctor@ddht.demo", "password": "doctor123"}).status_code == 200
