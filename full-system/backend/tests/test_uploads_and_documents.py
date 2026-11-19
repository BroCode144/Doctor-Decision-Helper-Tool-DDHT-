"""Security tests 6-9 and suite items 13-18 (uploads + PDF pipeline)."""

import pymupdf

from app.modules.ai import vector_store
from tests.conftest import logs, pdf_bytes, upload


# --- Test 7 / 14: doctor uploads to an authorized patient ------------------
def test_doctor_upload_authorized_patient_succeeds(client, doctor, admin):
    r = upload(client, doctor, patient_id="P001", document_type="CONSULTATION", title="Consult note Sept",
               description="Follow-up note")
    assert r.status_code == 201, r.text
    d = r.json()["document"]
    assert d["patient_id"] == "P001" and d["uploader_role"] == "DOCTOR" and d["record_id"]
    assert d["extraction_status"] == "EXTRACTED" and d["index_status"] == "INDEXED" and d["chunk_count"] >= 1
    rec = client.get(f"/patients/P001/records/{d['record_id']}", headers=doctor).json()
    assert rec["doctor"]["id"] == "D001"
    assert logs(client, admin, action="DOCUMENT_UPLOADED")[0]["resource_id"] == d["id"]


# --- Test 6 / 16: doctor uploads to an unauthorized patient ---------------
def test_doctor_upload_unauthorized_patient_rejected(client, doctor, admin):
    from tests.conftest import login

    other = login(client, "anjali@ddht.demo", "doctor123")  # D002: P003 never gave consent
    for h, pid in [(doctor, "P002"), (other, "P003")]:
        reason = "Patient has not authorized this doctor."
        r = upload(client, h, patient_id=pid)
        assert r.status_code == 403
        assert r.json()["detail"]["reason"] == reason
    assert len(logs(client, admin, action="DOCUMENT_UPLOAD_REJECTED")) == 2
    # nothing stored for P002 beyond the seed document
    from app.db.session import SessionLocal
    from app.models import Document
    from sqlalchemy import select, func
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(Document).where(Document.patient_id == "P002")) == 1


def test_doctor_upload_after_revocation_rejected(client, doctor, patient):
    client.delete("/patients/P001/consent/D001", headers=patient)
    assert upload(client, doctor, patient_id="P001").status_code == 403


def test_doctor_upload_requires_patient(client, doctor):
    assert upload(client, doctor).status_code == 422


# --- Test 8 / 13: patient uploads -------------------------------------------
def test_patient_upload_own(client, patient):
    r = upload(client, patient, title="My lab report")
    assert r.status_code == 201
    d = r.json()["document"]
    assert d["patient_id"] == "P001" and d["uploader_role"] == "PATIENT"
    docs = client.get("/patients/P001/documents", headers=patient).json()
    assert d["id"] in {x["id"] for x in docs}
    dl = client.get(f"/documents/{d['id']}/download", headers=patient)
    assert dl.status_code == 200 and dl.content.startswith(b"%PDF-")
    assert dl.headers["x-content-type-options"] == "nosniff"


def test_patient_upload_for_other_patient_rejected(client, patient, admin):
    r = upload(client, patient, patient_id="P002")
    assert r.status_code == 403
    assert logs(client, admin, action="DOCUMENT_UPLOAD_REJECTED")


# --- Test 9 / 15: admin uploads ---------------------------------------------
def test_admin_administrative_upload(client, admin):
    r = upload(client, admin, category="ADMINISTRATIVE", document_type="OTHER", title="Data retention policy")
    assert r.status_code == 201
    d = r.json()["document"]
    assert d["patient_id"] is None and d["category"] == "ADMINISTRATIVE" and d["index_status"] == "SKIPPED"
    assert client.get(f"/documents/{d['id']}/download", headers=admin).status_code == 200
    ops = logs(client, admin, action="ADMIN_OPERATION")
    assert ops[0]["resource_id"] == d["id"]


def test_admin_patient_upload_requires_permission_and_reason(client, admin, admin_limited, doctor):
    # missing justification
    assert upload(client, admin, patient_id="P002").status_code == 422
    # admin without explicit permission
    r = upload(client, admin_limited, patient_id="P002", admin_reason="Scanned from hospital front desk")
    assert r.status_code == 403
    # permitted admin with justification
    r = upload(client, admin, patient_id="P002", admin_reason="Paper report delivered to records office")
    assert r.status_code == 201
    d = r.json()["document"]
    assert d["patient_id"] == "P002" and d["uploader_role"] == "ADMIN"
    ops = logs(client, admin, action="ADMIN_OPERATION", patient_id="P002")
    assert "Justification" in ops[0]["reason"]
    # admin still cannot read its content
    assert client.get(f"/documents/{d['id']}", headers=admin, params={"include_text": True}).status_code == 403
    # and a doctor without authorization still cannot read it
    assert client.get(f"/documents/{d['id']}", headers=doctor).status_code == 403


def test_patients_and_doctors_cannot_upload_administrative(client, patient, doctor):
    assert upload(client, patient, category="ADMINISTRATIVE").status_code == 403
    assert upload(client, doctor, patient_id="P001", category="ADMINISTRATIVE").status_code == 403


# --- 17: PDF extraction -------------------------------------------------------
def test_pdf_extraction_chunking_and_chroma_metadata(client, patient):
    lines = ["Vitamin D (25-OH): 18 ng/mL (reference 30-100) LOW"] + [f"Line {i} of padding text for chunking." for i in range(80)]
    r = upload(client, patient, data=pdf_bytes(lines), title="Vitamin D report", document_type="LAB_REPORT")
    d = r.json()["document"]
    assert d["page_count"] >= 1 and d["chunk_count"] >= 2
    full = client.get(f"/documents/{d['id']}", headers=patient, params={"include_text": True}).json()
    assert "Vitamin D (25-OH): 18 ng/mL" in full["extracted_text"]
    got = vector_store._collection().get(where={"document_id": d["id"]}, include=["metadatas"])
    assert len(got["ids"]) == d["chunk_count"]
    meta = got["metadatas"][0]
    assert meta["patient_id"] == "P001" and meta["record_id"] == d["record_id"]
    assert meta["document_id"] == d["id"] and meta["record_type"] == "LAB_REPORT" and meta["date"] == "2026-09-01"


# --- 18: corrupt / empty / scanned / unsupported ---------------------------
def test_corrupt_pdf_rejected_gracefully(client, patient):
    r = upload(client, patient, data=b"%PDF-1.7\n this is not really a pdf \x00\x01")
    assert r.status_code == 422
    assert r.json()["detail"]["code"] in ("PDF_CORRUPT", "PDF_EXTRACTION_FAILED")
    assert "Traceback" not in r.text


def test_empty_pdf_and_scanned_pdf_stored_with_warning(client, patient):
    doc = pymupdf.open()
    doc.new_page()
    empty = doc.tobytes()
    r = upload(client, patient, data=empty)
    assert r.status_code == 201
    assert r.json()["document"]["extraction_status"] == "EMPTY"
    assert "no text" in r.json()["message"]

    png = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 40, 40), False).tobytes("png")
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_image(pymupdf.Rect(50, 50, 300, 300), stream=png)
    r = upload(client, patient, data=doc.tobytes())
    assert r.status_code == 201
    assert r.json()["document"]["extraction_status"] == "SCANNED_NO_TEXT"
    assert "scanned" in r.json()["message"]


def test_unsupported_and_spoofed_files_rejected(client, patient):
    assert upload(client, patient, data=b"#!/bin/sh\nrm -rf /", filename="evil.sh", mime="text/x-sh").status_code == 415
    assert upload(client, patient, data=b"MZ\x90\x00", filename="report.pdf").status_code == 422  # magic mismatch
    assert upload(client, patient, data=b"", filename="report.pdf").status_code == 422
    assert upload(client, patient, filename="report.pdf", mime="text/html").status_code == 415


def test_oversized_upload_rejected(client, patient):
    big = b"%PDF-1.4\n" + b"0" * (10 * 1024 * 1024 + 10)
    r = upload(client, patient, data=big)
    assert r.status_code == 413


def test_path_traversal_filename_is_neutralized(client, patient):
    r = upload(client, patient, filename="../../../../etc/passwd.pdf")
    assert r.status_code == 201
    d = r.json()["document"]
    assert d["filename"] == "passwd.pdf"
    from app.db.session import SessionLocal
    from app.models import Document
    with SessionLocal() as db:
        stored = db.get(Document, d["id"])
        assert ".." not in stored.storage_path and stored.storage_path.startswith("patients/P001/")
        assert stored.filename != "passwd.pdf"


def test_storage_rejects_traversal_keys():
    import pytest

    from app.shared.storage import StorageError, get_storage

    with pytest.raises(StorageError):
        get_storage().read("../../etc/passwd.pdf")


def test_image_upload_stored_not_indexed(client, patient):
    png = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 10, 10), False).tobytes("png")
    r = upload(client, patient, data=png, filename="xray.png", mime="image/png", document_type="IMAGING")
    assert r.status_code == 201
    d = r.json()["document"]
    assert d["extraction_status"] == "NOT_APPLICABLE" and d["index_status"] == "SKIPPED"


def test_upload_to_other_patients_record_rejected(client, patient):
    # REC-010 belongs to P002
    assert upload(client, patient, record_id="REC-010").status_code == 404


def test_document_not_found(client, patient):
    assert client.get("/documents/DOC-NOPE", headers=patient).status_code == 404
