"""Doctor applications: apply with documents -> automatic check -> admin decision -> email link -> set password."""

import re

import fitz
import pytest

from app.core.config import get_settings
from app.modules.doctors import doctor_documents as dd
NAME = "Dr. Kavita Menon"


def pdf(*lines: str) -> bytes:
    d = fitz.open()
    p = d.new_page()
    for i, line in enumerate(lines):
        p.insert_text((50, 60 + 20 * i), line, fontsize=11)
    return d.tobytes()


def docs(name="Kavita Menon", reg="MMC-2015-04471", council="Maharashtra Medical Council", year=2015, aadhaar="XXXX XXXX 4821"):
    return {
        "registration_certificate": ("reg.pdf", pdf(council, "Certificate of Registration", f"This is to certify that Dr. {name}",
                                                   "has been registered as a Registered Medical Practitioner",
                                                   f"Registration No: {reg}", f"Date of registration: 12/06/{year}"), "application/pdf"),
        "degree_certificate": ("mbbs.pdf", pdf("University of Mumbai", f"{name}", "has been admitted to the degree of",
                                              "Bachelor of Medicine and Bachelor of Surgery (M.B.B.S.)", f"Convocation {year - 1}"), "application/pdf"),
        "photo_id": ("id.pdf", pdf("Unique Identification Authority of India", "Government of India", name,
                                   "Date of Birth: 14/02/1990", f"Aadhaar: {aadhaar}"), "application/pdf"),
    }


FIELDS = {"full_name": NAME, "email": "kavita.menon@example.com", "specialization": "General Physician",
          "qualification": "MBBS", "council": "MH", "registration_number": "MMC-2015-04471", "registration_year": "2015"}


def apply(client, fields=None, files=None):
    return client.post("/doctor-applications", data={**FIELDS, **(fields or {})}, files=files if files is not None else docs())


def outbox() -> list[str]:
    d = get_settings().outbox_dir
    return [p.read_text() for p in sorted(d.glob("*.txt"))] if d.exists() else []


def last_link(path: str) -> str:
    for mail in reversed(outbox()):
        m = re.search(re.escape(path) + r"#token=([\w-]+)", mail)
        if m:
            return m.group(1)
    raise AssertionError("no link emailed")


@pytest.fixture(autouse=True)
def _clean_outbox():
    d = get_settings().outbox_dir
    for p in d.glob("*.txt") if d.exists() else []:
        p.unlink()


def make_doctor(client, admin, *, email, name="Dr. Arjun Iyer", reg="LIC-COLLEGE-01", password="doctor2026",
                specialization="Endocrinologist"):
    """Helper for other tests: a brand-new doctor the new way. Returns the login headers."""
    plain = name.replace("Dr. ", "")
    r = client.post("/doctor-applications", files=docs(name=plain, reg=reg),
                    data={**FIELDS, "full_name": name, "email": email, "registration_number": reg, "specialization": specialization})
    assert r.status_code == 201, r.text
    ref = r.json()["reference"]
    assert client.post(f"/admin/doctor-applications/{ref}/approve", headers=admin, json={}).status_code == 200
    assert client.post("/auth/set-password", json={"token": last_link("/set-password"), "password": password}).status_code == 200
    tok = client.post("/auth/login", json={"email": email, "password": password}).json()["access_token"]
    return {"Authorization": f"Bearer {tok}"}


# ---------------------------------------------------------------------------
def test_rules_spot_the_right_document_and_mismatches():
    t = "\n".join(["Maharashtra Medical Council", "Registered Medical Practitioner", "Registration No: MMC-2015-04471", "Dr. Kavita Menon 2015"])
    assert dd.looks_like("REGISTRATION", t) and not dd.looks_like("DEGREE", t)
    assert dd.name_match("Dr. Kavita Menon", "KAVITA MENON") == "ok"
    assert dd.name_match("Dr. Kavita R. Menon", "Kavita Menon") == "ok"  # middle initial ignored
    assert dd.name_match("Kavita Menon", "Rahul Sharma") == "no"
    assert not dd.looks_like("PHOTO_ID", "Hotel Sagar restaurant bill total Rs 231 thank you visit again")


def test_full_journey_apply_check_approve_set_password_login(client, admin):
    r = apply(client)
    assert r.status_code == 201, r.text
    ref = r.json()["reference"]
    assert "received" in outbox()[0] and ref in outbox()[0]
    # no account before approval
    assert client.post("/auth/login", json={"email": FIELDS["email"], "password": "anything1"}).status_code == 401
    # the background check ran: everything matches -> admin queue
    st = client.get("/doctor-applications/status", params={"reference": ref, "email": FIELDS["email"]}).json()
    assert st["status"] == "UNDER_REVIEW"
    full = client.get(f"/admin/doctor-applications/{ref}", headers=admin).json()
    assert full["checks"]["counts"]["fail"] == 0, full["checks"]
    labels = {c["label"]: c["result"] for d in full["checks"]["documents"] for c in d["checks"]}
    assert labels["Registration number matches"] == "ok" and labels["Council matches"] == "ok"
    assert full["nmc_register_url"].startswith("https://www.nmc.org.in")
    photo = next(d for d in full["documents"] if d["kind"] == "PHOTO_ID")
    assert client.get(f"/admin/doctor-applications/{ref}/documents/{photo['id']}", headers=admin).status_code == 200
    # approve -> doctor account (verified) + set-password email; photo ID deleted
    assert client.post(f"/admin/doctor-applications/{ref}/approve", headers=admin, json={"note": "Checked on NMC register"}).status_code == 200
    assert client.get(f"/admin/doctor-applications/{ref}/documents/{photo['id']}", headers=admin).status_code == 410
    token = last_link("/set-password")
    assert client.post("/auth/set-password", json={"token": token, "password": "short"}).status_code == 422
    assert client.post("/auth/set-password", json={"token": token, "password": "menon2026x"}).status_code == 200
    assert client.post("/auth/set-password", json={"token": token, "password": "again2026x"}).status_code == 400  # one use only
    tok = client.post("/auth/login", json={"email": FIELDS["email"], "password": "menon2026x"}).json()["access_token"]
    me = client.get("/users/me", headers={"Authorization": f"Bearer {tok}"}).json()
    assert me["role"] == "DOCTOR" and me["doctor"]["verification_status"] == "VERIFIED"


def test_wrong_document_or_full_aadhaar_asks_the_doctor_again(client, admin):
    files = docs(aadhaar="4821 7730 1956")  # full Aadhaar number visible
    files["degree_certificate"] = ("cv.pdf", pdf("CURRICULUM VITAE", "Kavita Menon", "Skills: teaching, research", "Hobbies: music"), "application/pdf")
    ref = apply(client, files=files).json()["reference"]
    full = client.get(f"/admin/doctor-applications/{ref}", headers=admin).json()
    assert full["status"] == "NEEDS_INFO"
    assert set(full["info_request"]["kinds"]) == {"DEGREE", "PHOTO_ID"}
    assert "masked" in outbox()[-1].lower()
    # the photo ID's text is never kept
    token = last_link("/doctor/reupload")
    info = client.post("/doctor-applications/reupload/info", json={"token": token}).json()
    assert {k["kind"] for k in info["kinds"]} == {"DEGREE", "PHOTO_ID"}
    good = docs()
    r = client.post("/doctor-applications/reupload", data={"token": token},
                    files={"degree_certificate": good["degree_certificate"], "photo_id": good["photo_id"]})
    assert r.status_code == 200, r.text
    assert client.get(f"/admin/doctor-applications/{ref}", headers=admin).json()["status"] == "UNDER_REVIEW"


def test_mismatches_are_flagged_for_the_admin_not_rejected(client, admin):
    files = docs(reg="MMC-2015-99999", council="Gujarat Medical Council")
    ref = apply(client, files=files).json()["reference"]
    full = client.get(f"/admin/doctor-applications/{ref}", headers=admin).json()
    assert full["status"] == "UNDER_REVIEW"
    fails = {c["label"] for d in full["checks"]["documents"] for c in d["checks"] if c["result"] == "fail"}
    assert {"Registration number matches", "Council matches"} <= fails


def test_admin_can_ask_for_more_and_reject(client, admin):
    ref = apply(client).json()["reference"]
    r = client.post(f"/admin/doctor-applications/{ref}/request-info", headers=admin,
                    json={"kinds": ["REGISTRATION"], "message": "The scan is too blurry to read the number."})
    assert r.status_code == 200 and r.json()["status"] == "NEEDS_INFO"
    assert "blurry" in outbox()[-1]
    r = client.post(f"/admin/doctor-applications/{ref}/reject", headers=admin, json={"reason": "Not found on the NMC register."})
    assert r.status_code == 200 and "Not found on the NMC register" in outbox()[-1]
    assert client.post(f"/admin/doctor-applications/{ref}/approve", headers=admin, json={}).status_code == 409


def test_validation_duplicates_and_permissions(client, admin, doctor, patient):
    assert apply(client, files={k: v for k, v in docs().items() if k != "photo_id"}).status_code == 422  # missing document
    assert apply(client, fields={"claims_specialist": "true"}).status_code == 422  # specialist needs a PG degree
    assert apply(client, fields={"email": "doctor@ddht.demo"}).status_code == 409  # existing account
    assert apply(client).status_code == 201
    assert apply(client).status_code == 409  # one open application per email
    ref = apply(client, fields={"email": "other@example.com"}).json()["reference"]
    dup = client.get(f"/admin/doctor-applications/{ref}", headers=admin).json()["checks"]["overall"]
    assert any(c["label"] == "Registration number not already used" and c["result"] == "fail" for c in dup)
    for h in (doctor, patient):
        assert client.get("/admin/doctor-applications", headers=h).status_code == 403
    assert client.get("/doctor-applications/status", params={"reference": ref, "email": "wrong@example.com"}).status_code == 404
    # the old self-registration path is closed for doctors
    r = client.post("/auth/register", json={"email": "x@example.com", "password": "doctor2026", "full_name": "Dr X", "role": "DOCTOR"})
    assert r.status_code == 422 and r.json()["detail"]["code"] == "DOCTORS_MUST_APPLY"


def test_new_link_only_for_approved_doctors_without_a_password(client, admin):
    make_doctor(client, admin, email="set.already@example.com", reg="REG-77001")
    n = len(outbox())
    client.post("/auth/set-password/new-link", json={"email": "set.already@example.com"})  # password already set
    client.post("/auth/set-password/new-link", json={"email": "doctor@ddht.demo"})  # seeded doctor
    client.post("/auth/set-password/new-link", json={"email": "nobody@example.com"})
    assert len(outbox()) == n
