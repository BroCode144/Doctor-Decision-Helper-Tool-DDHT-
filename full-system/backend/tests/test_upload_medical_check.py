"""Patients can upload medical documents only. Rules decide (no LLM); the local model only reads photos."""

import fitz
import pytest

from app.modules.records import medical_check
from app.modules.records.medical_check import judge_text


def _pdf(*lines):
    d = fitz.open()
    p = d.new_page()
    for i, line in enumerate(lines):
        p.insert_text((50, 60 + 20 * i), line, fontsize=12)
    return d.tobytes()


def _upload(client, headers, data, name="file.pdf", mime="application/pdf", **form):
    return client.post("/documents/upload", headers=headers, files={"file": (name, data, mime)},
                       data={"title": "Test", "document_type": "LAB_REPORT", "category": "MEDICAL", **form})


@pytest.mark.parametrize("text,expected", [
    ("Complete Blood Count\nPatient name: R. Sharma\nHaemoglobin 13.1 g/dL (13.0-17.0)\nPlatelets 2.5 lakhs/cumm\nWBC 7200 /cumm", "MEDICAL"),
    ("Dr. A. Kulkarni MBBS\nCity Clinic\nRx\nTab Paracetamol 500 mg 1-1-1 x 3 days\nReview after 5 days", "MEDICAL"),
    ("Vaccination Certificate\nName: Aman Patel\nVaccine: Hepatitis B\nDose 1: 12/01/2026\nGiven at: Health Centre", "MEDICAL"),
    ("CURRICULUM VITAE\nRahul Sharma\nSoftware Engineer\nSkills: Python, React, SQL\nEducation: B.Tech 2012", "NOT_MEDICAL"),
    ("INDIAN RAILWAYS E-TICKET\nPNR: 4521889012\nTrain 12951 Mumbai Rajdhani\nCoach B2 Berth 34\nFare: Rs 3,415", "NOT_MEDICAL"),
    ("HDFC Bank - Account Statement\nAccount No: XXXX4521\nSalary credit 85,000\nClosing balance 1,23,400", "NOT_MEDICAL"),
    ("ok", "UNSURE"),  # almost no text (e.g. an X-ray picture): never rejected
])
def test_rules(text, expected):
    assert judge_text(text, "pdf text").status == expected


def test_patient_cannot_upload_a_non_medical_pdf(client, patient, admin):
    r = _upload(client, patient, _pdf("CURRICULUM VITAE", "Rahul Sharma", "Software Engineer, 5 years", "Skills: Python, React"))
    assert r.status_code == 422 and r.json()["detail"]["code"] == "NOT_A_MEDICAL_DOCUMENT"
    assert "curriculum vitae" in r.json()["detail"]["message"].lower()


def test_patient_medical_pdf_is_accepted_and_marked(client, patient):
    r = _upload(client, patient, _pdf("Liver Function Test", "Patient: Rahul Sharma", "ALT (SGPT): 32 U/L (reference 7 - 56)",
                                      "AST (SGOT): 29 U/L (reference 10 - 40)", "Sample collected: 2026-09-18"))
    assert r.status_code in (200, 201), r.text
    assert r.json()["document"]["content_check"] == "MEDICAL"


def test_photo_without_the_reader_is_accepted_but_marked_not_checked(client, patient):
    png = fitz.open(stream=_pdf("Haemoglobin 13.1 g/dL"), filetype="pdf")[0].get_pixmap().tobytes("png")
    r = _upload(client, patient, png, name="report.png", mime="image/png")
    assert r.status_code in (200, 201), r.text
    assert r.json()["document"]["content_check"] == "NOT_CHECKED" and "not running" in r.json()["document"]["content_check_note"]


def test_photo_text_read_locally_is_judged_by_the_rules(client, patient, monkeypatch):
    png = fitz.open(stream=_pdf("x"), filetype="pdf")[0].get_pixmap().tobytes("png")
    monkeypatch.setattr(medical_check, "_read_image", lambda b: "Hotel Sagar Veg Restaurant Table 4 Masala Dosa Rs 180 Total Rs 231")
    r = _upload(client, patient, png, name="bill.png", mime="image/png")
    assert r.status_code == 422 and r.json()["detail"]["code"] == "NOT_A_MEDICAL_DOCUMENT"
    monkeypatch.setattr(medical_check, "_read_image", lambda b: "Dr. Mehta MBBS, City Clinic. Rx: Tab Amlodipine 5 mg OD. Review after 2 weeks")
    r = _upload(client, patient, png, name="rx.png", mime="image/png")
    assert r.status_code in (200, 201) and r.json()["document"]["content_check"] == "MEDICAL"


def test_doctor_uploads_are_not_checked(client, doctor):
    r = _upload(client, doctor, _pdf("CURRICULUM VITAE", "Rahul Sharma", "Software Engineer, 5 years", "Skills: Python"), patient_id="P001")
    assert r.status_code in (200, 201), r.text
    assert r.json()["document"]["content_check"] is None
