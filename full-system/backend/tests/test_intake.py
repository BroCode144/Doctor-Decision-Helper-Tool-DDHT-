"""Check-in by reception, a visit's symptoms and vitals, health background, local patterns, consent at booking."""

from datetime import datetime, timedelta, timezone

from app.db.session import SessionLocal
from app.models import Appointment, AppointmentStatus, Patient
from tests.conftest import login, logs

TZ = {"tz": "UTC"}


def make_appt(patient_id="P002", doctor_id="D001", starts_in=1, status=AppointmentStatus.CONFIRMED,
              reason="Fever and headache for 3 days"):
    start = datetime.now(timezone.utc) + timedelta(minutes=starts_in)
    with SessionLocal() as db:
        a = Appointment(patient_id=patient_id, doctor_id=doctor_id, start_at=start, end_at=start + timedelta(minutes=20),
                        status=status, reason=reason, patient_timezone="UTC",
                        created_by_user_id=db.get(Patient, patient_id).user_id)
        db.add(a)
        db.commit()
        return a.id


def reception(client):
    return login(client, "reception@ddht.demo", "reception123")


def notifications(client, headers):
    return client.get("/notifications", headers=headers).json()["items"]


def test_reception_sees_today_without_reasons_and_checks_in(client, doctor, admin):
    appt = make_appt()
    rh = reception(client)
    data = client.get("/reception/appointments", headers=rh, params=TZ).json()
    row = next(a for a in data["appointments"] if a["id"] == appt)
    assert row["patient"]["name"] == "Priya Shah" and row["can_check_in"] and not row["checked_in"]
    assert "reason" not in row and "Fever" not in str(row)  # the booking reason stays between patient and doctor
    assert "CHEST_PAIN_SWEATING" in data["red_flags"]

    r = client.post(f"/reception/appointments/{appt}/check-in", headers=rh, params=TZ,
                    json={"symptoms": "Fever, body pain, headache", "duration": "3 days", "severity": "moderate",
                          "systolic_bp": 118, "diastolic_bp": 76, "pulse": 96, "temperature_c": 38.6, "spo2": 98})
    assert r.status_code == 201, r.text
    assert r.json()["urgent"] == []
    row = next(a for a in client.get("/reception/appointments", headers=rh, params=TZ).json()["appointments"]
               if a["id"] == appt)
    assert row["checked_in"] and row["entries"][0]["author_role"] == "RECEPTION" and row["vitals"][0]["pulse"] == 96
    assert logs(client, admin, action="CHECK_IN_RECORDED")


def test_red_flags_alert_the_doctor_without_details(client, doctor):
    appt = make_appt()
    r = client.post(f"/reception/appointments/{appt}/check-in", headers=reception(client), params=TZ,
                    json={"symptoms": "Chest pain", "red_flags": ["CHEST_PAIN_SWEATING"], "spo2": 88})
    urgent = r.json()["urgent"]
    assert "Chest pain with sweating or breathlessness" in urgent and "Oxygen saturation below 90%" in urgent
    note = next(n for n in notifications(client, doctor) if n["kind"] == "URGENT_CHECK_IN")
    assert "Priya Shah" in note["title"] and "Chest" not in str(note) and note["link"].endswith(appt)


def test_check_in_rules(client):
    rh = reception(client)
    tomorrow = make_appt(starts_in=60 * 30)
    cancelled = make_appt(starts_in=5, status=AppointmentStatus.CANCELLED)
    today = make_appt(starts_in=10)
    assert client.post(f"/reception/appointments/{tomorrow}/check-in", headers=rh, params=TZ,
                       json={"symptoms": "x"}).status_code == 404
    assert client.post(f"/reception/appointments/{cancelled}/check-in", headers=rh, params=TZ,
                       json={"symptoms": "x"}).json()["detail"]["code"] == "INVALID_STATE"
    assert client.post(f"/reception/appointments/{today}/check-in", headers=rh, params=TZ,
                       json={}).json()["detail"]["code"] == "EMPTY_CHECK_IN"
    assert client.post(f"/reception/appointments/{today}/check-in", headers=rh, params=TZ,
                       json={"red_flags": ["MADE_UP"]}).status_code == 422
    assert client.post(f"/reception/appointments/{today}/check-in", headers=rh, params=TZ,
                       json={"spo2": 140}).status_code == 422


def test_reception_cannot_reach_anything_else(client):
    rh = reception(client)
    for path in ("/patients", "/patients/P001", "/patients/P001/records", "/patients/P001/history",
                 "/patients/P001/intake", "/appointments", "/documents/DOC-001", "/admin/stats", "/access-logs"):
        r = client.get(path, headers=rh)
        assert r.status_code == 403, path
    assert client.post("/ai/patients/P001/summary", headers=rh).status_code == 403
    assert client.get("/users/me", headers=rh).json()["role"] == "RECEPTION"
    assert client.get("/notifications", headers=rh).status_code == 200


def test_doctor_sees_the_visit_without_consent_and_adds_symptoms(client, doctor, patient2, admin):
    # D001 has no consent from P002 (revoked) but this is D001's appointment: the visit is visible, records are not.
    appt = make_appt()
    client.post(f"/reception/appointments/{appt}/check-in", headers=reception(client), params=TZ,
                json={"symptoms": "Fever, body pain", "temperature_c": 38.4})
    assert client.get("/patients/P002/records", headers=doctor).status_code == 403
    visit = client.get(f"/appointments/{appt}/intake", headers=doctor).json()
    roles = [e["author_role"] for e in visit["entries"]]
    assert roles == ["PATIENT", "RECEPTION"] and visit["entries"][0]["from_booking"] and visit["vitals"][0]["temperature_c"] == 38.4
    r = client.post(f"/appointments/{appt}/symptoms", headers=doctor, json={"text": "Pain behind the eyes", "duration": "2 days"})
    assert r.status_code == 201 and r.json()["author_role"] == "DOCTOR"
    assert [e["author_role"] for e in client.get(f"/appointments/{appt}/intake", headers=patient2).json()["entries"]] == \
        ["PATIENT", "RECEPTION", "DOCTOR"]
    assert logs(client, admin, action="SYMPTOMS_ADDED")
    # Another doctor, or another patient, cannot see this visit.
    other = login(client, "anjali@ddht.demo", "doctor123")
    assert client.get(f"/appointments/{appt}/intake", headers=other).status_code == 404
    assert client.get(f"/appointments/{appt}/intake", headers=login(client, "patient@ddht.demo", "patient123")).status_code == 404


def test_intake_across_visits_needs_consent(client, doctor, patient):
    appt = make_appt(patient_id="P001")
    client.post(f"/reception/appointments/{appt}/check-in", headers=reception(client), params=TZ,
                json={"symptoms": "Headache", "systolic_bp": 150})
    data = client.get("/patients/P001/intake", headers=doctor).json()
    assert data["latest_vitals"]["systolic_bp"] == 150 and any(e["text"] == "Headache" for e in data["entries"])
    assert client.get("/patients/P002/intake", headers=doctor).status_code == 403  # no consent
    r = client.post("/patients/P001/symptoms", headers=doctor, json={"text": "Mild dizziness", "appointment_id": appt})
    assert r.status_code == 201
    assert client.post("/patients/P001/symptoms", headers=doctor,
                       json={"text": "x y", "appointment_id": make_appt(patient_id="P003", starts_in=200)}).status_code == 404


def test_health_background(client, doctor, patient, patient2, patient3):
    h = client.get("/patients/P001/history", headers=doctor).json()
    assert h["allergy_status"] == "RECORDED" and h["allergies"][0]["name"] == "Penicillin"
    assert h["surgeries"] and h["family"]
    assert client.get("/patients/P002/history", headers=patient2).json()["allergy_status"] == "NONE_KNOWN"
    assert client.get("/patients/P003/history", headers=patient3).json()["allergy_status"] == "NOT_RECORDED"
    # Adding a real allergy replaces "no known allergies".
    h = client.post("/patients/P002/history", headers=patient2, json={"kind": "ALLERGY", "name": "Sulfa drugs", "detail": "Hives"}).json()
    assert h["allergy_status"] == "RECORDED" and h["no_known_allergies"] is None
    assert client.post("/patients/P002/history", headers=patient2, json={"kind": "NO_KNOWN_ALLERGIES"}).status_code == 409
    assert client.post("/patients/P003/history", headers=patient3, json={"kind": "SURGERY", "name": ""}).status_code == 422
    # Patients cannot remove what a doctor added; doctors need consent.
    doc_item = next(c for c in client.get("/patients/P001/history", headers=patient).json()["conditions"]
                    if c["added_by_role"] == "DOCTOR")
    assert client.delete(f"/patients/P001/history/{doc_item['id']}", headers=patient).status_code == 403
    assert client.delete(f"/patients/P001/history/{doc_item['id']}", headers=doctor).status_code == 200
    assert client.get("/patients/P002/history", headers=doctor).status_code == 403
    assert client.get("/patients/P001/history", headers=patient2).status_code == 403


def test_local_disease_patterns_admin_only(client, admin, doctor):
    rows = client.get("/admin/local-diseases", headers=admin).json()
    assert any(r["city"] == "Mumbai" and r["disease"] == "Dengue" for r in rows)
    r = client.post("/admin/local-diseases", headers=admin, json={"city": "Hyderabad", "disease": "Viral fever",
                                                                   "start_month": 11, "end_month": 2, "source": "Clinic data"})
    assert r.status_code == 201
    assert client.delete(f"/admin/local-diseases/{r.json()['id']}", headers=admin).status_code == 200
    assert client.get("/admin/local-diseases", headers=doctor).status_code == 403
    assert client.post("/admin/local-diseases", headers=admin, json={"city": "X", "disease": "Y", "start_month": 13,
                                                                      "end_month": 2, "source": "s"}).status_code == 422


def test_booking_can_share_records(client, doctor, patient2):
    from tests.test_appointments import ANSWERS, set_hours, slots

    set_hours(client, doctor)
    assert client.get("/patients/P002/records", headers=doctor).status_code == 403
    start = slots(client, patient2)[0]["start_at"]
    r = client.post("/appointments", headers=patient2, json={"doctor_id": "D001", "start_at": start, "reason": "Check-up",
                                                             "timezone": "Asia/Kolkata", "share_records": True,
                                                             "answers": {**ANSWERS, "pregnant": "no"}})
    assert r.status_code == 201, r.text
    assert client.get("/patients/P002/records", headers=doctor).status_code == 200
