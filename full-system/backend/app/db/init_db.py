"""Create the schema and load FICTIONAL demo data.

    python -m app.db.init_db           # create tables + seed if empty
    python -m app.db.init_db --reset   # drop everything, recreate, reseed

Seed PDFs are generated with PyMuPDF and pushed through the real upload
pipeline (validation -> extraction -> chunking -> embeddings -> Chroma).
All people, records and values are fictional.
"""

import argparse
import shutil
from datetime import date, datetime, time, timedelta, timezone

import pymupdf as fitz
from sqlalchemy import select, text

from app.modules.ai import vector_store
from app.core.config import BACKEND_DIR, get_settings
from app.core.security import hash_password
from app.db.session import Base, SessionLocal, engine
from app.models import (
    RECORD_STATUSES,
    Admin,
    HealthHistoryItem,
    LocalDiseasePattern,
    ConsentStatus,
    Consultation,
    Diagnosis,
    Doctor,
    DoctorAvailability,
    DoctorPatientRelationship,
    DoctorVerification,
    Hospital,
    MedicalRecord,
    Patient,
    PatientDoctorConsent,
    Prescription,
    RecordStatus,
    RecordType,
    Role,
    User,
    VerificationStatus,
)
from app.modules.records.documents import UploadRequest, upload_document


def make_pdf(title: str, lines: list[str]) -> bytes:
    doc = fitz.open()
    page = doc.new_page()
    y = 60
    page.insert_text((50, y), title, fontsize=15)
    y += 30
    for line in lines:
        if y > 780:
            page = doc.new_page()
            y = 60
        page.insert_text((50, y), line, fontsize=10.5)
        y += 17
    data = doc.tobytes()
    doc.close()
    return data


def _user(db, email, pw, name, role):
    u = User(email=email, password_hash=hash_password(pw), full_name=name, role=role,
             email_verified_at=datetime.now(timezone.utc))  # demo accounts count as confirmed
    db.add(u)
    db.flush()
    return u


def seed(db) -> None:
    for code, desc in RECORD_STATUSES.items():
        db.merge(RecordStatus(code=code, description=desc))

    h1 = Hospital(id="H001", name="City Care Hospital", city="Mumbai")
    h2 = Hospital(id="H002", name="Sunrise Multispecialty Hospital", city="Mumbai")
    h3 = Hospital(id="H003", name="Lakeside Medical Center", city="Ahmedabad")
    h4 = Hospital(id="H004", name="City Diagnostics Lab", city="Mumbai")
    db.add_all([h1, h2, h3, h4])

    # --- Admins -----------------------------------------------------------
    a1 = _user(db, "admin@ddht.demo", "admin123", "Meera Joshi", Role.ADMIN)
    db.add(Admin(id="A001", user_id=a1.id, can_manage_patient_documents=True))
    a2 = _user(db, "records.admin@ddht.demo", "admin123", "Karan Verma", Role.ADMIN)
    db.add(Admin(id="A002", user_id=a2.id, can_manage_patient_documents=False))

    # --- Doctors ----------------------------------------------------------
    doctors = {}
    for did, email, name, spec, lic, hosp, status in [
        ("D001", "doctor@ddht.demo", "Dr. Raj Mehta", "General Physician", "MCI-GP-48210", "H001", VerificationStatus.VERIFIED),
        ("D002", "anjali@ddht.demo", "Dr. Anjali Shah", "Cardiologist", "MCI-CD-19934", "H002", VerificationStatus.VERIFIED),
        ("D003", "vikram@ddht.demo", "Dr. Vikram Patel", "Orthopedic Surgeon", "MCI-OS-58822", "H003", VerificationStatus.PENDING),
    ]:
        u = _user(db, email, "doctor123", name, Role.DOCTOR)
        d = Doctor(id=did, user_id=u.id, specialization=spec, license_number=lic, hospital_id=hosp, verification_status=status)
        db.add(d)
        db.flush()
        db.add(DoctorVerification(doctor_id=did, status=status, reviewed_by_user_id=a1.id if status == VerificationStatus.VERIFIED else None,
                                  notes="Seed: license verified" if status == VerificationStatus.VERIFIED else "Seed: awaiting verification"))
        doctors[did] = (u, d)

    # --- Patients ---------------------------------------------------------
    patients = {}
    for pid, email, name, dob, gender, blood, phone, addr, emerg in [
        ("P001", "patient@ddht.demo", "Rahul Sharma", date(1990, 4, 12), "Male", "O+", "+91 90210 44556",
         "14 Palm Residency, Andheri West, Mumbai", "Sunita Sharma (Spouse) +91 90210 44557"),
        ("P002", "priya@ddht.demo", "Priya Shah", date(1988, 11, 2), "Female", "A+", "+91 98700 12233",
         "22 Green Meadows, Bandra East, Mumbai", "Kunal Shah (Brother) +91 98700 12244"),
        ("P003", "aman@ddht.demo", "Aman Patel", date(1995, 6, 25), "Male", "B+", "+91 91234 55667",
         "9 Hillview Apartments, Satellite, Ahmedabad", "Rina Patel (Mother) +91 91234 55668"),
    ]:
        u = _user(db, email, "patient123", name, Role.PATIENT)
        p = Patient(id=pid, user_id=u.id, date_of_birth=dob, gender=gender, blood_group=blood, phone=phone,
                    address=addr, emergency_contact=emerg)
        db.add(p)
        patients[pid] = (u, p)
    db.flush()

    # --- Previous visits + consent (the access matrix) --------------------
    now = datetime.now(timezone.utc)
    visits = [  # doctor, patient, first, last, count
        ("D001", "P001", date(2026, 3, 14), date(2026, 8, 25), 3),
        ("D001", "P002", date(2026, 6, 10), date(2026, 6, 10), 1),
        ("D002", "P001", date(2026, 4, 18), date(2026, 4, 18), 1),
        ("D002", "P002", date(2026, 7, 2), date(2026, 7, 2), 1),
        ("D003", "P003", date(2026, 5, 5), date(2026, 5, 5), 1),
    ]
    for d, p, first, last, n in visits:
        db.add(DoctorPatientRelationship(doctor_id=d, patient_id=p, first_visit_date=first, last_visit_date=last, visit_count=n))
    consents = [  # patient, doctor, status
        ("P001", "D001", ConsentStatus.GRANTED),
        ("P001", "D002", ConsentStatus.GRANTED),
        ("P002", "D001", ConsentStatus.REVOKED),
        ("P002", "D002", ConsentStatus.GRANTED),
        ("P003", "D001", ConsentStatus.GRANTED),  # consent but NO previous visit -> access (consent decides)
        ("P003", "D003", ConsentStatus.GRANTED),
    ]
    for p, d, st in consents:
        db.add(PatientDoctorConsent(
            patient_id=p, doctor_id=d, status=st, granted_at=now - timedelta(days=60),
            revoked_at=(now - timedelta(days=20)) if st == ConsentStatus.REVOKED else None))
    db.flush()

    # --- Structured records ----------------------------------------------
    def record(rid, pid, did, hid, rtype, title, d, desc):
        r = MedicalRecord(id=rid, patient_id=pid, doctor_id=did, hospital_id=hid, record_type=rtype, title=title,
                          record_date=d, description=desc, status="ACTIVE",
                          created_by_user_id=doctors[did][0].id if did else patients[pid][0].id)
        db.add(r)
        db.flush()
        return r

    record("REC-001", "P001", "D001", "H001", RecordType.CONSULTATION, "Consultation — cough and fever", date(2026, 3, 14),
           "Initial consultation for persistent dry cough and mild fever.")
    db.add(Consultation(id="CON-001", patient_id="P001", doctor_id="D001", hospital_id="H001", record_id="REC-001",
                        consultation_date=date(2026, 3, 14), reason="Persistent dry cough and mild fever for 5 days",
                        notes="Temperature 38.1 C. Throat mildly congested. Chest clear on auscultation. SpO2 98%. "
                              "Advised rest and fluids. CBC ordered.", follow_up="Review in 1 week if not improved"))
    db.add(Diagnosis(id="DIA-001", patient_id="P001", doctor_id="D001", record_id="REC-001", diagnosis_date=date(2026, 3, 14),
                     condition="Acute upper respiratory tract infection", notes="Likely viral; self-limiting.", status="Resolved"))
    db.add(Prescription(id="RX-001", patient_id="P001", doctor_id="D001", record_id="REC-001", prescribed_date=date(2026, 3, 14),
                        medication="Paracetamol 500 mg", dosage="1 tablet every 6 hours as needed, 5 days",
                        instructions="Take after food. Stop once fever subsides.", status="Completed"))
    db.add(Prescription(id="RX-005", patient_id="P001", doctor_id="D001", record_id="REC-001", prescribed_date=date(2026, 3, 14),
                        medication="Ambroxol 30 mg/5 ml syrup", dosage="5 ml three times daily, 5 days",
                        instructions="For cough. Take after food.", status="Completed"))
    db.add(Prescription(id="RX-006", patient_id="P001", doctor_id="D001", record_id="REC-001", prescribed_date=date(2026, 3, 14),
                        medication="Oral rehydration salts", dosage="1 sachet in 1 litre of water, sip through the day, 3 days",
                        instructions="Drink plenty of fluids while the fever lasts.", status="Completed"))

    record("REC-003", "P001", "D002", "H002", RecordType.CONSULTATION, "Cardiology screening", date(2026, 4, 18),
           "Annual cardiac screening; elevated blood pressure noted.")
    db.add(Consultation(id="CON-002", patient_id="P001", doctor_id="D002", hospital_id="H002", record_id="REC-003",
                        consultation_date=date(2026, 4, 18), reason="Routine cardiac screening",
                        notes="BP 146/94 mmHg (repeat 142/92). Pulse 78 regular. ECG and lipid profile ordered. "
                              "Lifestyle counselling given.", follow_up="Review with lipid results"))
    db.add(Diagnosis(id="DIA-002", patient_id="P001", doctor_id="D002", record_id="REC-003", diagnosis_date=date(2026, 4, 18),
                     condition="Essential hypertension, stage 1", notes="Documented on two readings.", status="Active"))
    db.add(Prescription(id="RX-002", patient_id="P001", doctor_id="D002", record_id="REC-003", prescribed_date=date(2026, 4, 18),
                        medication="Amlodipine 5 mg", dosage="1 tablet once daily",
                        instructions="Morning dose. Home BP log weekly.", status="Replaced"))

    record("REC-007", "P001", "D001", "H001", RecordType.CONSULTATION, "Follow-up — blood pressure review", date(2026, 8, 25),
           "Follow-up visit reviewing blood pressure and repeat lipid profile.")
    db.add(Consultation(id="CON-003", patient_id="P001", doctor_id="D001", hospital_id="H001", record_id="REC-007",
                        consultation_date=date(2026, 8, 25), reason="Blood pressure and lipid follow-up",
                        notes="BP 132/84 mmHg on amlodipine. Reports daily 30-minute walks. Repeat lipid panel reviewed.",
                        follow_up="Review in 3 months"))
    db.add(Prescription(id="RX-003", patient_id="P001", doctor_id="D001", record_id="REC-007", prescribed_date=date(2026, 8, 25),
                        medication="Amlodipine 5 mg (continued)", dosage="1 tablet once daily",
                        instructions="Continue current dose.", status="Active"))
    db.add(Prescription(id="RX-007", patient_id="P001", doctor_id="D001", record_id="REC-007", prescribed_date=date(2026, 8, 25),
                        medication="Atorvastatin 10 mg", dosage="1 tablet at night",
                        instructions="Started after the repeat lipid profile. Tell the doctor about any muscle pain.", status="Active"))

    record("REC-010", "P002", "D001", "H001", RecordType.CONSULTATION, "Consultation — seasonal allergy", date(2026, 6, 10),
           "Seasonal allergy symptoms.")
    db.add(Consultation(id="CON-004", patient_id="P002", doctor_id="D001", hospital_id="H001", record_id="REC-010",
                        consultation_date=date(2026, 6, 10), reason="Sneezing and nasal congestion",
                        notes="Seasonal pattern. No wheeze.", follow_up="None"))
    db.add(Diagnosis(id="DIA-003", patient_id="P002", doctor_id="D001", record_id="REC-010", diagnosis_date=date(2026, 6, 10),
                     condition="Allergic rhinitis", notes="Seasonal.", status="Managed"))
    db.add(Prescription(id="RX-004", patient_id="P002", doctor_id="D001", record_id="REC-010", prescribed_date=date(2026, 6, 10),
                        medication="Cetirizine 10 mg", dosage="1 tablet at night, 10 days", instructions="May cause drowsiness.",
                        status="Completed"))
    record("REC-011", "P002", "D002", "H002", RecordType.CONSULTATION, "Consultation — palpitations", date(2026, 7, 2),
           "Evaluation of intermittent palpitations.")
    db.add(Consultation(id="CON-005", patient_id="P002", doctor_id="D002", hospital_id="H002", record_id="REC-011",
                        consultation_date=date(2026, 7, 2), reason="Intermittent palpitations",
                        notes="ECG normal sinus rhythm. Thyroid function test ordered.", follow_up="Review with TSH"))

    record("REC-020", "P003", "D003", "H003", RecordType.CONSULTATION, "Consultation — knee injury", date(2026, 5, 5),
           "Right knee pain after football injury.")
    db.add(Consultation(id="CON-006", patient_id="P003", doctor_id="D003", hospital_id="H003", record_id="REC-020",
                        consultation_date=date(2026, 5, 5), reason="Right knee pain after sports injury",
                        notes="Medial joint line tenderness. MRI ordered.", follow_up="Physiotherapy referral"))
    db.add(Diagnosis(id="DIA-004", patient_id="P003", doctor_id="D003", record_id="REC-020", diagnosis_date=date(2026, 5, 5),
                     condition="Grade I medial collateral ligament sprain (right knee)", notes="Conservative care.", status="Improving"))
    db.commit()

    # --- Documents through the REAL pipeline ------------------------------
    D001_user, P001_user = doctors["D001"][0], patients["P001"][0]
    D002_user, P002_user, P003_user = doctors["D002"][0], patients["P002"][0], patients["P003"][0]
    docs = [
        (P001_user, "P001", "DOC-001", "REC-002", RecordType.LAB_REPORT, date(2026, 3, 16), "Complete Blood Count — March 2026",
         "CBC ordered during respiratory infection.",
         ["City Diagnostics Lab — Laboratory Report (FICTIONAL DEMO DATA)", "Patient: Rahul Sharma (P001)",
          "Sample collected: 2026-03-16", "Test: Complete Blood Count (CBC) with CRP", "",
          "Hemoglobin: 13.1 g/dL (reference 13.0 - 17.0)", "Total WBC count: 11,800 /uL (reference 4,000 - 11,000) HIGH",
          "Neutrophils: 72 %", "Lymphocytes: 21 %", "Platelet count: 240,000 /uL (reference 150,000 - 410,000)",
          "C-reactive protein (CRP): 18 mg/L (reference < 5) HIGH", "",
          "Lab comment: Mild leukocytosis and raised CRP noted."]),
        (P001_user, "P001", "DOC-002", "REC-004", RecordType.LAB_REPORT, date(2026, 4, 20), "Lipid Profile and HbA1c — April 2026",
         "Lipid profile ordered at cardiology screening.",
         ["City Diagnostics Lab — Laboratory Report (FICTIONAL DEMO DATA)", "Patient: Rahul Sharma (P001)",
          "Sample collected: 2026-04-20 (fasting 12 hours)", "Test: Lipid profile, fasting glucose, HbA1c", "",
          "Total cholesterol: 232 mg/dL (desirable < 200) HIGH", "LDL cholesterol: 158 mg/dL (optimal < 100) HIGH",
          "HDL cholesterol: 41 mg/dL (reference > 40)", "Triglycerides: 190 mg/dL (normal < 150) HIGH",
          "Fasting plasma glucose: 104 mg/dL (reference 70 - 99) HIGH", "HbA1c: 5.8 % (reference < 5.7) HIGH",
          "", "Lab comment: Values flagged against laboratory reference ranges."]),
        (D002_user, "P001", "DOC-003", "REC-005", RecordType.IMAGING, date(2026, 4, 22), "Echocardiogram Report",
         "Transthoracic echocardiogram.",
         ["Sunrise Multispecialty Hospital — Cardiac Imaging (FICTIONAL DEMO DATA)", "Patient: Rahul Sharma (P001)",
          "Study date: 2026-04-22", "Study: Transthoracic echocardiogram (2D Echo)", "",
          "Left ventricular ejection fraction: 60 %", "Left ventricular wall thickness: upper limit of normal (11 mm)",
          "Valves: structurally normal, no significant regurgitation", "Pericardium: no effusion", "",
          "Impression: Normal LV systolic function. Borderline LV wall thickness."]),
        (P001_user, "P001", "DOC-004", "REC-006", RecordType.LAB_REPORT, date(2026, 8, 20), "Lipid Profile and HbA1c — August 2026",
         "Repeat lipid profile before follow-up.",
         ["City Diagnostics Lab — Laboratory Report (FICTIONAL DEMO DATA)", "Patient: Rahul Sharma (P001)",
          "Sample collected: 2026-08-20 (fasting 12 hours)", "Test: Lipid profile, fasting glucose, HbA1c", "",
          "Total cholesterol: 205 mg/dL (desirable < 200) HIGH", "LDL cholesterol: 131 mg/dL (optimal < 100) HIGH",
          "HDL cholesterol: 45 mg/dL (reference > 40)", "Triglycerides: 160 mg/dL (normal < 150) HIGH",
          "Fasting plasma glucose: 98 mg/dL (reference 70 - 99)", "HbA1c: 5.6 % (reference < 5.7)",
          "", "Lab comment: Values flagged against laboratory reference ranges."]),
        (D001_user, "P001", "DOC-005", "REC-008", RecordType.DISCHARGE_SUMMARY, date(2025, 11, 6), "Discharge Summary — Dengue Fever",
         "Hospital admission November 2025.",
         ["City Care Hospital — Discharge Summary (FICTIONAL DEMO DATA)", "Patient: Rahul Sharma (P001)",
          "Admitted: 2025-11-02   Discharged: 2025-11-06", "Admitting doctor: Dr. Raj Mehta", "",
          "Presenting complaint: High fever, body ache and headache for 3 days.", "Dengue NS1 antigen: positive.",
          "Lowest platelet count during stay: 68,000 /uL (2025-11-04).", "Platelet count at discharge: 142,000 /uL.",
          "Treated with IV fluids and supportive care. No bleeding episodes.", "",
          "Discharge diagnosis: Dengue fever without warning signs (recovered).", "Condition at discharge: stable."]),
        (P002_user, "P002", "DOC-006", "REC-012", RecordType.LAB_REPORT, date(2026, 7, 4), "Thyroid Function Test",
         "TSH ordered for palpitations.",
         ["City Diagnostics Lab — Laboratory Report (FICTIONAL DEMO DATA)", "Patient: Priya Shah (P002)",
          "Sample collected: 2026-07-04", "TSH: 2.1 mIU/L (reference 0.4 - 4.0)", "Free T4: 1.2 ng/dL (reference 0.8 - 1.8)"]),
        (P003_user, "P003", "DOC-007", "REC-021", RecordType.IMAGING, date(2026, 5, 8), "MRI Right Knee",
         "MRI following sports injury.",
         ["Lakeside Medical Center — Radiology (FICTIONAL DEMO DATA)", "Patient: Aman Patel (P003)", "Study date: 2026-05-08",
          "Study: MRI right knee", "Findings: Grade I sprain of the medial collateral ligament. Menisci intact.",
          "Impression: Low-grade MCL sprain, no tear."]),
    ]
    for actor, pid, doc_id, rec_id, rtype, d, title, desc, lines in docs:
        db.add(MedicalRecord(id=rec_id, patient_id=pid,
                             doctor_id=actor.doctor.id if actor.doctor else None,
                             hospital_id=actor.doctor.hospital_id if actor.doctor else "H004",
                             record_type=rtype, title=title, record_date=d, description=desc, status="ACTIVE",
                             created_by_user_id=actor.id))
        db.commit()
        pdf = make_pdf(title, lines)
        upload_document(db, actor, UploadRequest(
            data=pdf, filename=f"{title}.pdf", content_type="application/pdf", patient_id=pid, record_id=rec_id,
            document_type=rtype.value, document_date=d, title=title, description=desc, document_id=doc_id))
    db.commit()
    seed_intake_demo(db)


def reset_storage() -> None:
    s = get_settings()
    if s.upload_dir.exists():
        shutil.rmtree(s.upload_dir)
    vector_store.reset_collection()


def run_migrations(conn) -> None:
    """Bring the schema to the latest Alembic revision."""
    from alembic import command
    from alembic.config import Config

    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.attributes["connection"] = conn
    command.upgrade(cfg, "head")


def seed_demo_availability(db) -> int:
    """Weekly hours for the demo doctors (only for doctors who have none yet). Returns rows added."""
    plan = {
        "D001": ([0, 1, 2, 3, 4], time(10, 0), time(13, 0), 20),  # Mon-Fri 10:00-13:00, 20-minute slots
        "D002": ([0, 2, 4], time(14, 0), time(17, 0), 30),        # Mon/Wed/Fri 14:00-17:00, 30-minute slots
    }
    added = 0
    for doctor_id, (days, start, end, minutes) in plan.items():
        if db.get(Doctor, doctor_id) is None:
            continue
        if db.scalar(select(DoctorAvailability).where(DoctorAvailability.doctor_id == doctor_id).limit(1)):
            continue
        for day in days:
            db.add(DoctorAvailability(doctor_id=doctor_id, weekday=day, start_time=start, end_time=end,
                                      slot_minutes=minutes, timezone="Asia/Kolkata"))
            added += 1
    db.commit()
    return added


# Example seasonal patterns for the demo hospitals' cities. NOT real surveillance data: replace them with IDSP
# outbreak data (or your own clinic's confirmed diagnoses) on the admin "Local diseases" page.
DEMO_LOCAL_PATTERNS = [
    ("Mumbai", "Dengue", 7, 11, "HIGH"), ("Mumbai", "Malaria", 6, 10, "MEDIUM"),
    ("Mumbai", "Leptospirosis", 6, 9, "MEDIUM"), ("Mumbai", "Viral fever / influenza-like illness", 11, 2, "HIGH"),
    ("Ahmedabad", "Dengue", 8, 11, "HIGH"), ("Ahmedabad", "Viral fever / influenza-like illness", 11, 2, "HIGH"),
]
DEMO_SOURCE = "Example for the demo; replace with IDSP data"


def seed_intake_demo(db) -> list[str]:
    """Reception account, health background and example local patterns. Safe to run on an existing database."""
    added = []
    if db.scalar(select(User).where(User.email == "reception@ddht.demo")) is None:
        _user(db, "reception@ddht.demo", "reception123", "Pooja Nair", Role.RECEPTION)
        added.append("reception account")
    if db.scalar(select(HealthHistoryItem).limit(1)) is None:
        users = {e: db.scalar(select(User).where(User.email == e)) for e in
                 ("patient@ddht.demo", "priya@ddht.demo", "aman@ddht.demo", "doctor@ddht.demo")}
        items = [
            ("P001", "patient@ddht.demo", "ALLERGY", "Penicillin", "Skin rash and itching (2018)"),
            ("P001", "patient@ddht.demo", "SURGERY", "Appendix removal (appendectomy)", "2012"),
            ("P001", "doctor@ddht.demo", "CONDITION", "Essential hypertension", "Since April 2026"),
            ("P001", "patient@ddht.demo", "FAMILY", "Heart attack", "Father, at 60"),
            ("P002", "priya@ddht.demo", "NO_KNOWN_ALLERGIES", "No known allergies", None),
            ("P003", "aman@ddht.demo", "SURGERY", "Right knee arthroscopy", "2023"),
        ]
        for pid, email, kind, name, detail in items:
            u = users[email]
            if u is not None and db.get(Patient, pid) is not None:
                db.add(HealthHistoryItem(patient_id=pid, kind=kind, name=name, detail=detail,
                                         added_by_user_id=u.id, added_by_role=u.role.value))
        added.append("health background")
    if db.scalar(select(LocalDiseasePattern).limit(1)) is None:
        for city, disease, start, end, level in DEMO_LOCAL_PATTERNS:
            db.add(LocalDiseasePattern(city=city, disease=disease, start_month=start, end_month=end, level=level,
                                       source=DEMO_SOURCE))
        added.append("example local disease patterns")
    db.commit()
    return added


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--reset", action="store_true", help="Drop all tables and storage, then reseed.")
    args = parser.parse_args()
    with engine.begin() as conn:
        if args.reset:
            Base.metadata.drop_all(conn)
            conn.execute(text("DROP TABLE IF EXISTS alembic_version"))
        run_migrations(conn)
    if args.reset:
        reset_storage()
    with SessionLocal() as db:
        if db.scalar(select(User).limit(1)) is None:
            seed(db)
            print("Seeded fictional demo data.")
        else:
            print("Database already contains data; skipping seed (use --reset to reseed).")
        added = seed_demo_availability(db)
        if added:
            print(f"Added demo availability ({added} weekly blocks) for the demo doctors.")
        extra = seed_intake_demo(db)
        if extra:
            print("Added: " + ", ".join(extra) + ".")
        tables = db.execute(text("SELECT count(*) FROM information_schema.tables WHERE table_schema='public'")).scalar()
        print(f"Tables in public schema: {tables}")


if __name__ == "__main__":
    main()
