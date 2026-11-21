"""Booking questions: required, validated per patient, stored, shown to the doctor and used by the risk models."""

from app.models import HealthAnswers
from app.modules.booking import questionnaire
from tests.test_appointments import ANSWERS, book, set_hours, slots


def _cad(client, doctor, **body):
    r = client.post("/decision-support/patients/P001/analyze", headers=doctor, json=body)
    assert r.status_code == 200, r.text
    return {s["id"]: s for s in r.json()["scores"]}["cad_cleveland"], r.json()


def test_questions_depend_on_the_patient(client, patient, patient2, doctor):
    q1 = client.get("/booking/questions", headers=patient).json()
    ids1 = {q["id"] for q in q1["questions"]}
    assert {"duration", "severity", "smoking", "diabetes", "bp_medicine", "chest_pain"} <= ids1
    assert "pregnant" not in ids1 and "sex" not in ids1  # P001 is male
    assert "pregnant" in {q["id"] for q in client.get("/booking/questions", headers=patient2).json()["questions"]}
    assert len(q1["red_flags"]) == 8
    assert client.get("/booking/questions", headers=doctor).status_code == 403


def test_booking_needs_symptoms_and_every_answer(client, doctor, patient, patient2):
    set_hours(client, doctor)
    start = slots(client, patient)[0]["start_at"]
    # no symptoms
    assert book(client, patient, start, reason="").status_code == 422
    # a missing answer is rejected, naming the question, and nothing is booked
    r = client.post("/appointments", headers=patient, json={"doctor_id": "D001", "start_at": start, "reason": "Cough",
                                                            "answers": {k: v for k, v in ANSWERS.items() if k != "smoking"}})
    assert r.status_code == 422 and "smoke" in r.json()["detail"]["message"].lower()
    assert client.get("/appointments", headers=patient).json() == []
    # red flags must be stated explicitly (an empty list = "none of these")
    no_flags = {k: v for k, v in ANSWERS.items() if k != "red_flags"}
    r = client.post("/appointments", headers=patient, json={"doctor_id": "D001", "start_at": start, "reason": "Cough", "answers": no_flags})
    assert r.status_code == 422
    # where the patient lives and recent travel are required on EVERY booking (they feed the local-disease facts)
    for q, word in (("city", "city"), ("travel", "travelled")):
        rest = {k: v for k, v in ANSWERS.items() if k != q}
        r = client.post("/appointments", headers=patient, json={"doctor_id": "D001", "start_at": start, "reason": "Cough", "answers": rest})
        assert r.status_code == 422 and word in r.json()["detail"]["message"].lower()
    # chest pain = yes needs the three follow-ups
    assert book(client, patient, start, answers={"chest_pain": "yes"}).status_code == 422
    # an invalid option is rejected
    assert book(client, patient, start, answers={"diabetes": "maybe"}).status_code == 422
    # the female patient must answer the pregnancy question
    r = client.post("/appointments", headers=patient2, json={"doctor_id": "D001", "start_at": start, "reason": "Cough", "answers": ANSWERS})
    assert r.status_code == 422 and "pregnant" in r.json()["detail"]["message"].lower()
    # severity is not needed for a check-up
    ok = book(client, patient, start, answers={"duration": "checkup", "severity": None})
    assert ok.status_code == 201, ok.text


def test_chest_pain_type_follows_the_diamond_forrester_rule():
    def t(**kw):
        a = HealthAnswers(**{"chest_pain": "yes", "cp_central": "yes", "cp_exertion": "yes", "cp_rest_relief": "yes", **kw})
        return questionnaire.chest_pain_type(a)[0]

    assert t() == 1  # 3 of 3: typical angina
    assert t(cp_rest_relief="no") == 2  # 2 of 3: atypical
    assert t(cp_exertion="no", cp_rest_relief="no") == 3  # 1 of 3: non-anginal
    assert t(cp_central="no", cp_exertion="no", cp_rest_relief="no") == 3
    assert t(cp_central="unsure") is None  # never guessed: the doctor chooses
    assert questionnaire.chest_pain_type(HealthAnswers(chest_pain="no"))[0] == 4


def test_answers_reach_the_doctor_and_the_models(client, doctor, patient):
    set_hours(client, doctor)
    a = book(client, patient, slots(client, patient)[0]["start_at"], reason="Chest tightness when climbing stairs",
             answers={"smoking": "now", "chest_pain": "yes", "cp_central": "yes", "cp_exertion": "yes", "cp_rest_relief": "yes"}).json()
    # the appointment's doctor sees the answers with the visit
    vi = client.get(f"/appointments/{a['id']}/intake", headers=doctor).json()
    assert vi["answers"]["chest_pain_type"]["value"] == 1
    assert {"label": "Smoking", "value": "smokes now"} in vi["answers"]["items"]
    assert vi["entries"][0]["duration"] == "1-4 weeks" and vi["entries"][0]["severity"] == "mild"
    # Decision Support uses the derived chest-pain type, saying where it came from
    cad, full = _cad(client, doctor)
    cp = next(i for i in cad["inputs"] if i["name"] == "chest_pain_type")
    assert cp["value"] == "Typical angina" and "booking answers" in cp["source"]
    assert "chest_pain_type" not in {m["name"] for m in cad["missing"]}
    assert full["answers"]["chest_pain_type"]["value"] == 1
    # the doctor's own entry always wins
    cad2, _ = _cad(client, doctor, chest_pain_type=3)
    assert next(i for i in cad2["inputs"] if i["name"] == "chest_pain_type")["source"] == "entered by doctor"


def test_red_flags_at_booking_alert_the_doctor_without_details(client, doctor, patient):
    set_hours(client, doctor)
    a = book(client, patient, slots(client, patient)[0]["start_at"], reason="Chest pain",
             answers={"red_flags": ["CHEST_PAIN_SWEATING"]}).json()
    notes = client.get("/notifications", headers=doctor).json()
    items = notes["items"] if isinstance(notes, dict) else notes
    urgent = [n for n in items if n["kind"] == "URGENT_BOOKING"]
    assert urgent and "chest" not in (urgent[0]["body"] or "").lower()
    vi = client.get(f"/appointments/{a['id']}/intake", headers=doctor).json()
    assert vi["entries"][0]["red_flags"][0]["code"] == "CHEST_PAIN_SWEATING"
    assert vi["urgent"]


def test_answers_move_with_a_rescheduled_appointment(client, doctor, patient):
    set_hours(client, doctor)
    s = slots(client, patient)
    a = book(client, patient, s[0]["start_at"]).json()
    new = client.patch(f"/appointments/{a['id']}", headers=patient, json={"start_at": s[1]["start_at"]})
    assert new.status_code == 200, new.text
    vi = client.get(f"/appointments/{new.json()['id']}/intake", headers=patient).json()
    assert vi["answers"] is not None


def test_city_and_travel_bring_in_those_cities_seasonal_diseases(client, doctor, patient, admin, fake_llm):
    # admin adds patterns for the patient's city and the place they visited (the hospital is in Mumbai)
    for city, disease in (("Pune", "Chikungunya"), ("Kochi", "Leptospirosis")):
        assert client.post("/admin/local-diseases", headers=admin, json={
            "city": city, "disease": disease, "start_month": 1, "end_month": 12, "source": "Test data"}).status_code == 201
    set_hours(client, doctor)
    # an unknown city name is rejected; "travel = yes" needs the place
    start = slots(client, patient)[0]["start_at"]
    assert book(client, patient, start, answers={"city": "Atlantis"}).status_code == 422
    assert book(client, patient, start, answers={"travel": "yes"}).status_code == 422
    a = book(client, patient, start, reason="Fever and joint pain for 3 days",
             answers={"city": "Pune", "travel": "yes", "travel_city": "Kochi"})
    assert a.status_code == 201, a.text
    vi = client.get(f"/appointments/{a.json()['id']}/intake", headers=doctor).json()
    assert {"label": "Lives in", "value": "Pune"} in vi["answers"]["items"]
    assert {"label": "Travelled to", "value": "Kochi"} in vi["answers"]["items"]
    out = client.post("/decision-support/patients/P001/conditions", headers=doctor, json={}).json()
    local = {f["city"]: f["text"] for f in out["facts"] if f["kind"] == "local"}
    assert "where the patient lives" in local["Pune"] and "travelled there" in local["Kochi"]
    assert "the hospital's city" in local["Mumbai"]


def test_city_list_has_coordinates_but_coordinates_are_never_accepted(client, patient):
    q = {x["id"]: x for x in client.get("/booking/questions", headers=patient).json()["questions"]}
    mumbai = next(o for o in q["city"]["options"] if o["value"] == "Mumbai")
    assert 18 < mumbai["lat"] < 20 and 72 < mumbai["lon"] < 74
    assert q["travel_city"]["only_if"] == {"travel": "yes"}
    cols = {c.name for c in HealthAnswers.__table__.columns}  # only city names are stored, never coordinates
    assert {"city", "travel", "travel_city"} <= cols and not any("lat" in c or "lon" in c for c in cols)
