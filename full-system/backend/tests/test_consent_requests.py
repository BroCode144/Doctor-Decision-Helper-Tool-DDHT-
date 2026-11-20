"""Doctors asking patients for access: request, approve, decline, cool-down, and who may do what."""

from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models import ConsentRequest
from tests.conftest import login, logs

REASON = "Referred to me for a cardiology second opinion"


def notifications(client, headers):
    return client.get("/notifications", headers=headers).json()["items"]


def ask(client, headers, pid="P003", reason=REASON):
    return client.post(f"/patients/{pid}/consent-requests", headers=headers, json={"reason": reason})


def test_request_then_approve_gives_access(client, doctor2, patient3, admin):
    access = client.get("/patients/P003/access", headers=doctor2).json()
    assert access["access"]["granted"] is False and access["consent_request"]["can_request"] is True

    r = ask(client, doctor2)
    assert r.status_code == 201 and r.json()["consent_request"]["status"] == "PENDING"
    assert ask(client, doctor2).json()["detail"]["code"] == "REQUEST_PENDING"  # one open request at a time
    state = client.get("/patients/P003/access", headers=doctor2).json()["consent_request"]
    assert state["status"] == "PENDING" and state["can_request"] is False

    # The patient is notified without the doctor's reason, and sees the reason only inside the portal.
    note = next(n for n in notifications(client, patient3) if n["kind"] == "CONSENT_REQUESTED")
    assert "Anjali" in note["title"] and REASON not in str(note) and note["link"] == "/patient/consent"
    pending = client.get("/patients/P003/consent-requests", headers=patient3).json()
    assert len(pending) == 1 and pending[0]["doctor"]["id"] == "D002" and pending[0]["reason"] == REASON

    r = client.post(f"/patients/P003/consent-requests/{pending[0]['id']}/approve", headers=patient3)
    assert r.status_code == 200 and r.json()["access"]["granted"] is True
    assert client.get("/patients/P003/records", headers=doctor2).status_code == 200
    assert client.get("/patients/P003/consent-requests", headers=patient3).json() == []
    assert any(n["kind"] == "CONSENT_APPROVED" for n in notifications(client, doctor2))
    assert logs(client, admin, action="CONSENT_REQUESTED") and logs(client, admin, action="CONSENT_GRANTED")
    # With access, there is nothing left to request.
    assert ask(client, doctor2).json()["detail"]["code"] == "ALREADY_HAS_ACCESS"


def test_decline_blocks_new_requests_for_seven_days(client, doctor2, patient3, admin):
    ask(client, doctor2)
    rid = client.get("/patients/P003/consent-requests", headers=patient3).json()[0]["id"]
    r = client.post(f"/patients/P003/consent-requests/{rid}/decline", headers=patient3)
    assert r.status_code == 200 and r.json()["access"]["granted"] is False
    assert client.get("/patients/P003/records", headers=doctor2).status_code == 403
    assert any(n["kind"] == "CONSENT_DECLINED" for n in notifications(client, doctor2))
    assert logs(client, admin, action="CONSENT_REQUEST_DECLINED")
    # Answered requests cannot be answered again.
    assert client.post(f"/patients/P003/consent-requests/{rid}/approve", headers=patient3).status_code == 409

    r = ask(client, doctor2)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "REQUEST_RECENTLY_DECLINED"
    assert r.json()["detail"]["retry_after"]
    with SessionLocal() as db:  # eight days later the doctor may ask again
        req = db.get(ConsentRequest, rid)
        req.responded_at = datetime.now(timezone.utc) - timedelta(days=8)
        db.commit()
    assert ask(client, doctor2).status_code == 201


def test_granting_from_the_consent_page_closes_the_open_request(client, doctor2, patient3):
    ask(client, doctor2)
    assert client.post("/patients/P003/consent/D002", headers=patient3).status_code == 200
    assert client.get("/patients/P003/consent-requests", headers=patient3).json() == []
    with SessionLocal() as db:
        statuses = db.scalars(select(ConsentRequest.status).where(ConsentRequest.doctor_id == "D002")).all()
    assert [s.value for s in statuses] == ["APPROVED"]


def test_who_may_request_and_answer(client, doctor, doctor2, patient, patient3, admin):
    # Unverified doctors cannot ask.
    pending_doctor = login(client, "vikram@ddht.demo", "doctor123")
    assert ask(client, pending_doctor).json()["detail"]["code"] == "DOCTOR_NOT_VERIFIED"
    # Only doctors can ask; only the patient can see and answer their requests.
    for h in (patient, admin):
        assert ask(client, h).status_code == 403
    ask(client, doctor2)
    rid = client.get("/patients/P003/consent-requests", headers=patient3).json()[0]["id"]
    for h in (patient, doctor2, admin):
        assert client.get("/patients/P003/consent-requests", headers=h).status_code == 403
        assert client.post(f"/patients/P003/consent-requests/{rid}/approve", headers=h).status_code == 403
    # A patient cannot answer someone else's request through their own record.
    assert client.post(f"/patients/P001/consent-requests/{rid}/approve", headers=patient).status_code == 404
    assert client.post(f"/patients/P003/consent-requests/{rid}/maybe", headers=patient3).status_code == 404
    assert ask(client, doctor2, pid="P999").status_code == 404
    assert ask(client, doctor2, reason="x" * 301).status_code == 422
    # Requesting gives no medical data.
    assert client.get("/patients/P003/records", headers=doctor2).status_code == 403
