"""The booking chat asks a limited number of questions, never asks for consent in the chat (that's a checkbox), and
the doctor gets a short "latest from the patient" summary of the most recent booking."""

from app.modules.booking import intake_engine as e
from tests.test_appointments import ANSWERS, set_hours, slots
from tests.test_intake_chat import talk, turn


def test_chat_is_short_and_never_asks_for_consent(client, patient):
    out = talk(client, patient, "I have had a dry cough and a mild fever")
    asked = 0
    while not out["done"] and asked < 40:
        assert "remaining" in out and out["remaining"] >= 0
        out = turn(client, patient, out["state"], "not sure")
        asked += 1
    assert out["done"] and asked <= e.MAX_QUESTIONS + 3  # a few warning-sign checks may come on top
    said = " ".join(m["text"] for m in out["state"]["messages"] if m["role"] == "assistant").lower()
    assert "may we save" not in said and "improve this service" not in said
    assert "consent_processing" not in out["state"]["form"]


def test_doctor_sees_a_summary_of_the_latest_booking(client, doctor, patient, patient2):
    set_hours(client, doctor)
    start = slots(client, patient)[0]["start_at"]
    form = {"main_symptoms_narrative": "Cough for a week", "cough": True, "fever_present": False, "trend": "worse",
            "consent_processing": True}
    r = client.post("/appointments", headers=patient, json={
        "doctor_id": "D001", "start_at": start, "reason": "Cough for a week", "answers": ANSWERS, "intake": {"form": form}})
    assert r.status_code == 201, r.text
    latest = client.get("/patients/P001/latest-from-patient", headers=doctor).json()["latest"]
    assert latest["appointment"]["id"] == r.json()["id"] and latest["updated_at"]
    text = " | ".join(latest["summary"])
    assert "Problem: Cough for a week" in text and "Warning signs: none reported" in text and "cough" in text.lower()
    assert latest["answers"] and latest["intake_record"]
    # needs record access, and patients can't call it
    assert client.get("/patients/P002/latest-from-patient", headers=doctor).status_code == 403
    assert client.get("/patients/P001/latest-from-patient", headers=patient).status_code == 403
