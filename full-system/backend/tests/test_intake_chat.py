"""Intake chat (chat only): fills the intake record silently, asks one natural question at a time (warning signs only
when they fit the problem, never a checklist), never reveals causes, scores home readings by device, asks about
family history, keeps the AI fenced in, works without it, and saves with consent."""

import json
from datetime import date, timedelta

import pytest

from app.core.deps import get_llm_factory
from app.main import app
from app.modules.booking import intake_engine as e
from tests.conftest import login, register
from tests.test_appointments import ANSWERS, set_hours, slots


def turn(client, h, state=None, message=None):
    r = client.post("/intake/chat", headers=h, json={"state": state, "message": message})
    assert r.status_code == 200, r.text
    return r.json()


def talk(client, h, *messages):
    out = turn(client, h)
    for m in messages:
        out = turn(client, h, out["state"], m)
    return out


def use_llm(llm):
    app.dependency_overrides[get_llm_factory] = lambda: (lambda: llm)


class ScriptedLLM:
    model = "scripted"

    def __init__(self, out):
        self.out, self.prompts = out, []

    def complete(self, system, user, max_tokens=900):
        assert "Never name, suggest, hint at or rule out any disease" in system
        self.prompts.append(user)
        return json.dumps(self.out(user) if callable(self.out) else self.out)


@pytest.fixture()
def new_patient(client):
    assert register(client, {"email": "kavya@college.edu", "password": "patient2026", "full_name": "Kavya Rao",
                             "role": "PATIENT"}).status_code == 201
    return login(client, "kavya@college.edu", "patient2026")


def test_contract_and_records_prefill(client, patient, doctor):
    out = turn(client, patient)
    assert {"assistant_message", "quick_replies", "silent_form_updates", "extracted_clinical_codes", "red_flag_triggered"} <= set(out)
    assert out["assistant_message"].startswith("Hello Rahul, welcome back")
    f = out["state"]["form"]
    assert f["drug_allergies"] == ["Penicillin"] and "hypertension" in f["chronic_conditions"] and f["gender"] == "male"
    assert f["parental_and_family_history"][0]["condition"] == "Heart attack"
    assert client.post("/intake/chat", headers=doctor, json={}).status_code == 403


def test_no_checklist_and_warning_signs_fit_the_problem(client, patient2):
    out = talk(client, patient2, "Fever of 102 for 3 days with body ache")
    f = out["state"]["form"]
    assert f["fever_present"] is True and f["highest_temp"]["value"] == 102 and f["highest_temp"]["unit"] == "°F"
    assert f["muscle_aches"] is True and f["duration_days"] == 3
    assert {"fever_present", "highest_temp", "muscle_aches"} <= set(out["silent_form_updates"])
    # one natural question about a warning sign that fits a fever, not a list
    assert out["state"]["targets"][0] in ("seizure_or_stiff_neck", "fluid_intolerance_low_urine", "confusion_fainting", "device:highest_temp")
    assert "any of these" not in out["assistant_message"].lower() and out["assistant_message"].count("?") <= 1
    # a cough doesn't bring up the stiff-neck question
    out2 = talk(client, patient2, "Dry cough since yesterday")
    asked = []
    for _ in range(3):
        asked.append(out2["state"]["targets"][0])
        out2 = turn(client, patient2, out2["state"], "No")
    assert "seizure_or_stiff_neck" not in asked and "severe_breathlessness" in asked


def test_warning_sign_about_myself_stops_at_once(client, patient):
    out = talk(client, patient, "I have chest pain right now and I'm sweating")
    assert out["red_flag_triggered"] and "108" in out["assistant_message"] and out["done"] and out["quick_replies"] == []


def test_warning_sign_about_someone_else_is_checked_first(client, patient):
    out = talk(client, patient, "I have a cough. My father had chest pain last year")
    assert not out["red_flag_triggered"] and out["state"]["targets"] == ["chest_pain"]
    assert "yourself" in out["assistant_message"] and out["state"]["form"].get("chest_discomfort") is None
    out = turn(client, patient, out["state"], "No")
    assert not out["red_flag_triggered"] and out["state"]["form"]["chest_pain"] is False


def test_contextual_warning_question_answered_yes_stops(client, patient2):
    out = talk(client, patient2, "Headache since yesterday")
    for _ in range(4):
        if out["state"]["targets"][0] == "seizure_or_stiff_neck":
            break
        out = turn(client, patient2, out["state"], "No")
    assert out["state"]["targets"][0] == "seizure_or_stiff_neck"
    out = turn(client, patient2, out["state"], "Yes")
    assert out["red_flag_triggered"]


def test_home_reading_asks_the_device_and_scores_it(client, patient):
    out = talk(client, patient, "Headache for 2 days, my BP was 160/100 this morning")
    assert out["state"]["form"]["home_bp"]["value"] == "160/100"
    assert out["state"]["form"]["home_bp"]["reliability_tier"] == "device_not_asked_yet"
    for _ in range(4):
        if out["state"]["targets"][0] == "device:home_bp":
            break
        out = turn(client, patient, out["state"], "No")
    assert out["state"]["targets"] == ["device:home_bp"] and "measure" in out["assistant_message"]
    out = turn(client, patient, out["state"], "on my Omron upper arm cuff")
    bp = out["state"]["form"]["home_bp"]
    assert bp["source_device"] == "Omron upper arm cuff" and bp["reliability_score"] == 0.92 and bp["reliability_tier"] == "high"
    # a device named in the same sentence is used straight away
    out = talk(client, patient, "Feeling dizzy, oxygen 93 on my noise smartwatch")
    assert out["state"]["form"]["home_spo2"]["reliability_tier"] == "low"


@pytest.mark.parametrize("vital,device,tier", [
    ("home_bp", "Omron upper arm BP machine", "high"), ("home_spo2", "Apple Watch", "moderate_high"),
    ("home_bp", "Apple Watch", "low"), ("home_hr", "₹1500 fitness band", "low"), ("home_glucose", "Accu-Chek glucometer", "high"),
    ("highest_temp", "forehead thermometer", "high"), ("home_spo2", "I don't remember", "unverified")])
def test_device_rubric(vital, device, tier):
    score, t = e.score_device(vital, device)
    low, high = {"high": (0.85, 1.0), "moderate_high": (0.70, 0.84), "low": (0.20, 0.45), "unverified": (0.10, 0.10)}[t]
    assert t == tier and low <= score <= high


def test_family_history_is_asked_for_hereditary_overlap(client, new_patient):
    out = talk(client, new_patient, "I feel tired all the time and I have gained weight since 2 months")
    seen = []
    for _ in range(16):
        seen.append(out["state"]["targets"][0])
        if seen[-1] == "parental_and_family_history":
            break
        out = turn(client, new_patient, out["state"], "No")
    assert "parental_and_family_history" in seen and "parents" in out["assistant_message"].lower()


def test_ai_reasoning_never_reaches_the_patient(client, patient2):
    use_llm(ScriptedLLM(lambda p: {
        "form_updates": {"trend": {"value": "worse", "quote": "getting worse"},
                         "cough": {"value": True, "quote": "Fever for 2 days"},
                         "headache": {"value": True, "quote": "terrible headache"},
                         "untreated_water": {"value": True, "quote": "maybe drank tap water"},
                         "appetite": {"value": "kind of low", "quote": "Fever"}},
        "assistant_message": "This could be dengue, so do you have joint pain?", "target_field": "joint_pain",
        "quick_replies": ["Yes", "Take rest"]}))
    out = talk(client, patient2, "Fever for 2 days, it is getting worse, I maybe drank tap water")
    f = out["state"]["form"]
    assert f["trend"] == "worse" and f["cough"] is True
    assert "headache" not in f and "untreated_water" not in f and "appetite" not in f
    assert "dengue" not in out["assistant_message"].lower() and "could be" not in out["assistant_message"].lower()
    for bad in ("This sounds like a thyroid problem. Do you feel cold?", "Do you have any of these: fever, rash, cough?",
                "Is it worse at night? Does it spread?", "You should rest. When did it start?",
                "Since malaria is common, have you had chills?"):
        assert e.guard(bad, target="chills") is None
    assert e.guard("Do you often feel colder than people around you?", target="cold_intolerance")
    assert e.guard("Has anyone in your family had thyroid problems or diabetes?", target="parental_and_family_history")


def test_ai_probe_is_used_when_safe(client, patient2):
    use_llm(ScriptedLLM(lambda p: {"form_updates": {},
                                   "assistant_message": "Thanks. Do you wake up sweaty at night?",
                                   "target_field": "night_sweats", "quick_replies": []}))
    out = talk(client, patient2, "I'm tired all the time and gaining weight since 2 months, it's about the same")
    for _ in range(6):
        if out["state"]["targets"][0] == "night_sweats":
            break
        out = turn(client, patient2, out["state"], "No")
    # night sweats isn't in any symptom group: the AI chose it as a probe, and it is counted
    assert out["state"]["targets"] == ["night_sweats"] and out["ai_used"] and out["state"]["probes"] == 1


def test_works_when_the_ai_is_down(client, patient):
    class Down:
        model = "down"

        def complete(self, *a, **k):
            from app.modules.ai.llm import LLMUnavailableError
            raise LLMUnavailableError()

    use_llm(Down())
    out = talk(client, patient, "Burning when I pee for 2 days")
    assert out["state"]["form"]["dysuria"] is True and not out["ai_used"] and out["assistant_message"].endswith("?")


def test_vague_onset_is_kept_in_their_words_and_not_asked_again(client, patient):
    out = talk(client, patient, "headache")
    while out["state"]["targets"][0] != "onset_date":
        out = turn(client, patient, out["state"], "No")
    out = turn(client, patient, out["state"], "past few days, not any precise number")
    assert out["state"]["form"]["onset_note"].startswith("past few days") and out["state"]["targets"][0] != "onset_date"


def test_word_rules():
    p, now, check = e.rule_patch("Fever since yesterday and chills, came back from Goa 5 days ago, no cough, and chest pain")
    assert p["onset_date"] == (date.today() - timedelta(days=1)).isoformat()
    assert p["travel_30d_3m_destination"] == "Goa" and "travel_3d" not in p
    assert p["chills"] is True and p["cough"] is False and now == ["chest_pain"]
    p, _, _ = e.rule_patch("no fever and no headache, but loose motions")
    assert p["fever_present"] is False and p["headache"] is False and p["diarrhea"] is True
    assert e.family_rows("my mother has thyroid and diabetes, and my father has high BP") == [
        {"relation": "mother", "condition": "Thyroid problem", "age_at_onset": ""},
        {"relation": "mother", "condition": "Diabetes", "age_at_onset": ""},
        {"relation": "father", "condition": "High blood pressure", "age_at_onset": ""}]
    assert "numbness_tingling" not in e.rule_patch("past few days, not any precise number")[0]
    p, now, check = e.rule_patch("I'm tired. My mother had a stroke and fainted years ago")
    assert p.get("fatigue") is True and now == [] and check == ["confusion_fainting"]


def _book(client, h, form):
    start = slots(client, h)[0]["start_at"]
    return client.post("/appointments", headers=h, json={"doctor_id": "D001", "start_at": start, "reason": "Fever",
                                                         "answers": {**ANSWERS, "pregnant": "no", "sex": "female"},
                                                         "intake": {"form": form}})


def test_booking_saves_the_intake_and_builds_a_new_patients_profile(client, doctor, new_patient):
    set_hours(client, doctor)
    form = {"main_symptoms_narrative": "Tired and gaining weight", "fatigue": True, "weight_gain": True,
            "onset_date": "2026-09-15", "gender": "female", "dob": "1994-02-03", "height_cm": 160, "weight_kg": 55,
            "drug_allergies": ["Sulfa"], "chronic_conditions": ["thyroid"], "water_source": "borewell",
            "home_bp": {"value": "128/84", "source_device": "Omron upper arm cuff"},
            "parental_and_family_history": [{"relation": "mother", "condition": "Thyroid problem", "age_at_onset": "40"}],
            "current_medicines": [{"drug_name": "Thyroxine", "dose": "50 mcg", "frequency": "daily", "reason": "thyroid"}],
            "consent_processing": True}
    r = _book(client, new_patient, form)
    assert r.status_code == 201, r.text
    vi = client.get(f"/appointments/{r.json()['id']}/intake", headers=doctor).json()
    rec = vi["intake_record"]
    assert rec and not rec["red_flag"] and {c["display"] for c in rec["codes"]} >= {"Fatigue", "Weight gain"}
    items = {i["label"]: i["value"] for s in rec["sections"] for i in s["items"]}
    assert items["Drinking water"] == "Borewell" and items["BMI"] == "21.5"
    assert "reliability 0.92" in items["Blood pressure"] and "Thyroid problem" in items["Parents' and family's illnesses"]
    c = client.get("/intake/context", headers=new_patient).json()
    assert c["context"]["returning"] and c["form"]["drug_allergies"] == ["Sulfa"] and c["form"]["dob"] == "1994-02-03"
    assert c["form"]["parental_and_family_history"][0]["condition"] == "Thyroid problem"
    assert any(m["drug_name"].startswith("Thyroxine") for m in c["form"]["current_medicines"])


def test_no_consent_means_nothing_saved(client, doctor, patient2):
    set_hours(client, doctor)
    r = _book(client, patient2, {"main_symptoms_narrative": "Cough", "cough": True, "consent_processing": False})
    vi = client.get(f"/appointments/{r.json()['id']}/intake", headers=doctor).json()
    assert vi["intake_record"] is None


def test_confirmed_red_flag_alerts_the_doctor(client, doctor, patient2):
    set_hours(client, doctor)
    r = _book(client, patient2, {"main_symptoms_narrative": "Fainted twice", "confusion_fainting": True, "consent_processing": True})
    notes = client.get("/notifications", headers=doctor).json()
    items = notes["items"] if isinstance(notes, dict) else notes
    urgent = [n for n in items if n["kind"] == "URGENT_BOOKING"]
    assert urgent and "faint" not in (urgent[0]["body"] or "").lower()
    vi = client.get(f"/appointments/{r.json()['id']}/intake", headers=doctor).json()
    assert vi["intake_record"]["red_flag"] and any("fainting" in u.lower() for u in vi["urgent"])
