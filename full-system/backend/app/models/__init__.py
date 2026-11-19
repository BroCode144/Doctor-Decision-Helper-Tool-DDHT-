"""SQLAlchemy ORM models for DDHT (PostgreSQL).

Tables: users, patients, doctors, admins, hospitals, medical_records, documents,
diagnoses, prescriptions, consultations, doctor_patient_relationships,
patient_doctor_consent, consent_requests, access_logs, doctor_verification, record_status,
doctor_availability, doctor_time_off, appointments, notifications, symptom_entries, vital_signs,
local_disease_patterns, health_history_items.
"""

import enum
import uuid
from datetime import date, datetime, timezone
from datetime import time as time_type

from sqlalchemy import (
    DDL,
    BigInteger,
    Boolean,
    Float,
    CheckConstraint,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
    Time,
    UniqueConstraint,
    event,
    text,
)
from sqlalchemy.dialects.postgresql import ExcludeConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def new_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:10].upper()}"


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------
class Role(str, enum.Enum):
    PATIENT = "PATIENT"
    DOCTOR = "DOCTOR"
    ADMIN = "ADMIN"
    RECEPTION = "RECEPTION"  # front desk / nurse: check-in only, never medical records


class RecordType(str, enum.Enum):
    DIAGNOSIS = "DIAGNOSIS"
    PRESCRIPTION = "PRESCRIPTION"
    CONSULTATION = "CONSULTATION"
    LAB_REPORT = "LAB_REPORT"
    IMAGING = "IMAGING"
    DISCHARGE_SUMMARY = "DISCHARGE_SUMMARY"
    MEDICAL_HISTORY = "MEDICAL_HISTORY"
    OTHER = "OTHER"


class DocumentCategory(str, enum.Enum):
    MEDICAL = "MEDICAL"
    ADMINISTRATIVE = "ADMINISTRATIVE"


class VerificationStatus(str, enum.Enum):
    PENDING = "PENDING"
    VERIFIED = "VERIFIED"
    REJECTED = "REJECTED"


class ConsentStatus(str, enum.Enum):
    GRANTED = "GRANTED"
    REVOKED = "REVOKED"


class ConsentRequestStatus(str, enum.Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    DECLINED = "DECLINED"


RECORD_STATUSES = {
    "ACTIVE": "Record is active and visible to authorized users.",
    "RESTRICTED": "Patient restricted this record; hidden from doctors and AI.",
    "ARCHIVED": "Record is archived (kept for history, not current).",
}


def _enum(e: type[enum.Enum], name: str) -> Enum:
    return Enum(e, name=name, native_enum=False, length=32, validate_strings=True)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )


# ---------------------------------------------------------------------------
# Identity
# ---------------------------------------------------------------------------
class User(TimestampMixin, Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=lambda: new_id("U"))
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(200), nullable=False)
    role: Mapped[Role] = mapped_column(_enum(Role, "role"), nullable=False, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    # Incremented on logout / deactivation -> invalidates all previously issued JWTs.
    token_version: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Set when the user typed the code emailed at sign-up. Patients cannot sign in before that.
    email_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    patient: Mapped["Patient | None"] = relationship(back_populates="user", uselist=False)
    doctor: Mapped["Doctor | None"] = relationship(back_populates="user", uselist=False)
    admin: Mapped["Admin | None"] = relationship(back_populates="user", uselist=False)


class EmailCode(Base):
    """A 6-digit code emailed to confirm an address. Only a keyed hash of the code is stored."""

    __tablename__ = "email_codes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    code_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    purpose: Mapped[str] = mapped_column(String(16), default="verify", server_default="verify", nullable=False)  # verify / reset
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class Hospital(TimestampMixin, Base):
    __tablename__ = "hospitals"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=lambda: new_id("H"))
    name: Mapped[str] = mapped_column(String(200), unique=True, nullable=False)
    city: Mapped[str | None] = mapped_column(String(120))


class Patient(TimestampMixin, Base):
    __tablename__ = "patients"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=lambda: new_id("P"))
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), unique=True, nullable=False)
    date_of_birth: Mapped[date | None] = mapped_column(Date)
    gender: Mapped[str | None] = mapped_column(String(32))
    phone: Mapped[str | None] = mapped_column(String(40))
    blood_group: Mapped[str | None] = mapped_column(String(8))
    address: Mapped[str | None] = mapped_column(String(300))
    emergency_contact: Mapped[str | None] = mapped_column(String(200))

    user: Mapped[User] = relationship(back_populates="patient", lazy="joined")

    @property
    def full_name(self) -> str:
        return self.user.full_name


class Doctor(TimestampMixin, Base):
    __tablename__ = "doctors"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=lambda: new_id("D"))
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), unique=True, nullable=False)
    specialization: Mapped[str] = mapped_column(String(120), nullable=False)
    license_number: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    hospital_id: Mapped[str | None] = mapped_column(ForeignKey("hospitals.id"))
    verification_status: Mapped[VerificationStatus] = mapped_column(
        _enum(VerificationStatus, "verification_status"), default=VerificationStatus.PENDING, nullable=False
    )

    user: Mapped[User] = relationship(back_populates="doctor", lazy="joined")
    hospital: Mapped[Hospital | None] = relationship(lazy="joined")

    @property
    def full_name(self) -> str:
        return self.user.full_name


class Admin(TimestampMixin, Base):
    __tablename__ = "admins"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=lambda: new_id("A"))
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), unique=True, nullable=False)
    # Explicit permission required before an admin may upload a document
    # that is attached to a patient (see ARCHITECTURE.md, admin model).
    can_manage_patient_documents: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    user: Mapped[User] = relationship(back_populates="admin", lazy="joined")


class DoctorVerification(Base):
    """History of verification decisions made by admins."""

    __tablename__ = "doctor_verification"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    doctor_id: Mapped[str] = mapped_column(ForeignKey("doctors.id", ondelete="CASCADE"), index=True, nullable=False)
    status: Mapped[VerificationStatus] = mapped_column(_enum(VerificationStatus, "verification_status"), nullable=False)
    reviewed_by_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


# ---------------------------------------------------------------------------
# Access control: patient consent (the previous visit is recorded for information)
# ---------------------------------------------------------------------------
class DoctorPatientRelationship(TimestampMixin, Base):
    """Records that a doctor has treated/visited a patient (previous visit)."""

    __tablename__ = "doctor_patient_relationships"
    __table_args__ = (
        UniqueConstraint("doctor_id", "patient_id", name="uq_relationship_doctor_patient"),
        CheckConstraint("visit_count >= 0", name="ck_relationship_visit_count"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    doctor_id: Mapped[str] = mapped_column(ForeignKey("doctors.id", ondelete="CASCADE"), index=True, nullable=False)
    patient_id: Mapped[str] = mapped_column(ForeignKey("patients.id", ondelete="CASCADE"), index=True, nullable=False)
    first_visit_date: Mapped[date | None] = mapped_column(Date)
    last_visit_date: Mapped[date | None] = mapped_column(Date)
    visit_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    @property
    def has_previous_visit(self) -> bool:
        return self.visit_count > 0 and self.first_visit_date is not None


class PatientDoctorConsent(TimestampMixin, Base):
    __tablename__ = "patient_doctor_consent"
    __table_args__ = (UniqueConstraint("patient_id", "doctor_id", name="uq_consent_patient_doctor"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    patient_id: Mapped[str] = mapped_column(ForeignKey("patients.id", ondelete="CASCADE"), index=True, nullable=False)
    doctor_id: Mapped[str] = mapped_column(ForeignKey("doctors.id", ondelete="CASCADE"), index=True, nullable=False)
    status: Mapped[ConsentStatus] = mapped_column(_enum(ConsentStatus, "consent_status"), nullable=False)
    granted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ConsentRequest(TimestampMixin, Base):
    """A doctor asking a patient for access. Approving it grants consent; the patient decides."""

    __tablename__ = "consent_requests"
    __table_args__ = (
        # At most one open request per doctor and patient.
        Index("uq_consent_requests_pending", "patient_id", "doctor_id", unique=True,
              postgresql_where=text("status = 'PENDING'")),
        Index("ix_consent_requests_patient_status", "patient_id", "status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    patient_id: Mapped[str] = mapped_column(ForeignKey("patients.id", ondelete="CASCADE"), nullable=False)
    doctor_id: Mapped[str] = mapped_column(ForeignKey("doctors.id", ondelete="CASCADE"), index=True, nullable=False)
    status: Mapped[ConsentRequestStatus] = mapped_column(_enum(ConsentRequestStatus, "consent_request_status"),
                                                         default=ConsentRequestStatus.PENDING, nullable=False)
    reason: Mapped[str | None] = mapped_column(String(300))  # shown to the patient in the portal, never in notifications
    responded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    doctor: Mapped["Doctor"] = relationship()


# ---------------------------------------------------------------------------
# Medical data
# ---------------------------------------------------------------------------
class RecordStatus(Base):
    __tablename__ = "record_status"

    code: Mapped[str] = mapped_column(String(16), primary_key=True)
    description: Mapped[str] = mapped_column(String(200), nullable=False)


class MedicalRecord(TimestampMixin, Base):
    __tablename__ = "medical_records"
    __table_args__ = (Index("ix_medical_records_patient_date", "patient_id", "record_date"),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=lambda: new_id("REC"))
    patient_id: Mapped[str] = mapped_column(ForeignKey("patients.id", ondelete="RESTRICT"), index=True, nullable=False)
    doctor_id: Mapped[str | None] = mapped_column(ForeignKey("doctors.id"))
    hospital_id: Mapped[str | None] = mapped_column(ForeignKey("hospitals.id"))
    record_type: Mapped[RecordType] = mapped_column(_enum(RecordType, "record_type"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(250), nullable=False)
    record_date: Mapped[date] = mapped_column(Date, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(ForeignKey("record_status.code"), default="ACTIVE", nullable=False)
    created_by_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"))

    doctor: Mapped[Doctor | None] = relationship(lazy="joined")
    hospital: Mapped[Hospital | None] = relationship(lazy="joined")
    documents: Mapped[list["Document"]] = relationship(back_populates="record")


class Document(Base):
    __tablename__ = "documents"
    __table_args__ = (
        CheckConstraint("size_bytes >= 0", name="ck_documents_size"),
        CheckConstraint(
            "(category = 'MEDICAL' AND patient_id IS NOT NULL) OR category = 'ADMINISTRATIVE'",
            name="ck_documents_medical_has_patient",
        ),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=lambda: new_id("DOC"))
    patient_id: Mapped[str | None] = mapped_column(ForeignKey("patients.id", ondelete="RESTRICT"), index=True)
    record_id: Mapped[str | None] = mapped_column(ForeignKey("medical_records.id"), index=True)
    uploaded_by: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    uploader_role: Mapped[Role] = mapped_column(_enum(Role, "role"), nullable=False)
    category: Mapped[DocumentCategory] = mapped_column(
        _enum(DocumentCategory, "document_category"), default=DocumentCategory.MEDICAL, nullable=False
    )
    title: Mapped[str] = mapped_column(String(250), nullable=False)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)  # safe server-side name
    storage_path: Mapped[str] = mapped_column(String(500), nullable=False)  # storage-backend key
    mime_type: Mapped[str] = mapped_column(String(100), nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    document_type: Mapped[RecordType] = mapped_column(_enum(RecordType, "record_type"), nullable=False)
    document_date: Mapped[date | None] = mapped_column(Date)
    description: Mapped[str | None] = mapped_column(Text)
    admin_reason: Mapped[str | None] = mapped_column(Text)
    upload_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    # PENDING / PROCESSED / PROCESSED_WITH_WARNINGS / FAILED
    processing_status: Mapped[str] = mapped_column(String(32), default="PENDING", nullable=False)
    # PENDING / EXTRACTED / EMPTY / SCANNED_NO_TEXT / NOT_APPLICABLE / FAILED
    extraction_status: Mapped[str] = mapped_column(String(32), default="PENDING", nullable=False)
    # PENDING / INDEXED / SKIPPED / FAILED
    index_status: Mapped[str] = mapped_column(String(32), default="PENDING", nullable=False)
    processing_message: Mapped[str | None] = mapped_column(Text)
    # Patient uploads only (app/modules/records/medical_check.py): MEDICAL, or NOT_CHECKED when it could not be confirmed.
    content_check: Mapped[str | None] = mapped_column(String(16))
    content_check_note: Mapped[str | None] = mapped_column(String(300))
    page_count: Mapped[int | None] = mapped_column(Integer)
    chunk_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    extracted_text: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    record: Mapped[MedicalRecord | None] = relationship(back_populates="documents")
    uploader: Mapped[User] = relationship(lazy="joined")


class Diagnosis(TimestampMixin, Base):
    __tablename__ = "diagnoses"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=lambda: new_id("DIA"))
    patient_id: Mapped[str] = mapped_column(ForeignKey("patients.id", ondelete="RESTRICT"), index=True, nullable=False)
    doctor_id: Mapped[str | None] = mapped_column(ForeignKey("doctors.id"))
    record_id: Mapped[str | None] = mapped_column(ForeignKey("medical_records.id"))
    diagnosis_date: Mapped[date] = mapped_column(Date, nullable=False)
    condition: Mapped[str] = mapped_column(String(250), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(40), default="Active", nullable=False)

    doctor: Mapped[Doctor | None] = relationship(lazy="joined")


class Prescription(TimestampMixin, Base):
    __tablename__ = "prescriptions"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=lambda: new_id("RX"))
    patient_id: Mapped[str] = mapped_column(ForeignKey("patients.id", ondelete="RESTRICT"), index=True, nullable=False)
    doctor_id: Mapped[str | None] = mapped_column(ForeignKey("doctors.id"))
    record_id: Mapped[str | None] = mapped_column(ForeignKey("medical_records.id"))
    prescribed_date: Mapped[date] = mapped_column(Date, nullable=False)
    medication: Mapped[str] = mapped_column(String(200), nullable=False)
    dosage: Mapped[str | None] = mapped_column(String(250))
    instructions: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(40), default="Active", nullable=False)

    doctor: Mapped[Doctor | None] = relationship(lazy="joined")


class Consultation(TimestampMixin, Base):
    __tablename__ = "consultations"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=lambda: new_id("CON"))
    patient_id: Mapped[str] = mapped_column(ForeignKey("patients.id", ondelete="RESTRICT"), index=True, nullable=False)
    doctor_id: Mapped[str | None] = mapped_column(ForeignKey("doctors.id"))
    hospital_id: Mapped[str | None] = mapped_column(ForeignKey("hospitals.id"))
    record_id: Mapped[str | None] = mapped_column(ForeignKey("medical_records.id"))
    consultation_date: Mapped[date] = mapped_column(Date, nullable=False)
    reason: Mapped[str] = mapped_column(String(300), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)
    follow_up: Mapped[str | None] = mapped_column(String(120))

    doctor: Mapped[Doctor | None] = relationship(lazy="joined")
    hospital: Mapped[Hospital | None] = relationship(lazy="joined")


# ---------------------------------------------------------------------------
# Audit
# ---------------------------------------------------------------------------
class AccessLog(Base):
    __tablename__ = "access_logs"
    __table_args__ = (
        Index("ix_access_logs_timestamp", "timestamp"),
        Index("ix_access_logs_action", "action"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), index=True)
    user_role: Mapped[str | None] = mapped_column(String(16))
    user_email: Mapped[str | None] = mapped_column(String(255))
    action: Mapped[str] = mapped_column(String(40), nullable=False)
    result: Mapped[str] = mapped_column(String(16), nullable=False)  # SUCCESS / DENIED / FAILURE
    patient_id: Mapped[str | None] = mapped_column(ForeignKey("patients.id"), index=True)
    resource_type: Mapped[str | None] = mapped_column(String(40))
    resource_id: Mapped[str | None] = mapped_column(String(64))
    reason: Mapped[str | None] = mapped_column(Text)
    ip_address: Mapped[str | None] = mapped_column(String(64))


# ---------------------------------------------------------------------------
# Online consultations: availability, appointments, notifications
# ---------------------------------------------------------------------------
# btree_gist lets one exclusion constraint combine "same doctor" (=) with
# "overlapping time range" (&&). Created before any table (create_all + Alembic).
event.listen(Base.metadata, "before_create", DDL("CREATE EXTENSION IF NOT EXISTS btree_gist"))


class AppointmentStatus(str, enum.Enum):
    REQUESTED = "REQUESTED"      # booked by the patient, waiting for the doctor
    CONFIRMED = "CONFIRMED"      # doctor accepted
    RESCHEDULED = "RESCHEDULED"  # replaced by a new appointment (rescheduled_from_id points back here)
    CANCELLED = "CANCELLED"      # cancelled / declined by patient or doctor
    IN_PROGRESS = "IN_PROGRESS"  # video consultation running (phase 2)
    COMPLETED = "COMPLETED"      # consultation took place (phase 2)
    NO_SHOW = "NO_SHOW"          # a participant did not attend (phase 2)


# Statuses that occupy a time slot (used by the overlap constraints).
ACTIVE_APPOINTMENT_STATUSES = ("REQUESTED", "CONFIRMED", "IN_PROGRESS")
_ACTIVE_SQL = "status IN ('REQUESTED', 'CONFIRMED', 'IN_PROGRESS')"


class DoctorAvailability(TimestampMixin, Base):
    """A weekly block of bookable hours, e.g. Monday 10:00-13:00 in 20-minute slots."""

    __tablename__ = "doctor_availability"
    __table_args__ = (
        CheckConstraint("weekday BETWEEN 0 AND 6", name="ck_availability_weekday"),
        CheckConstraint("start_time < end_time", name="ck_availability_times"),
        CheckConstraint("slot_minutes BETWEEN 5 AND 180", name="ck_availability_slot_minutes"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    doctor_id: Mapped[str] = mapped_column(ForeignKey("doctors.id", ondelete="CASCADE"), index=True, nullable=False)
    weekday: Mapped[int] = mapped_column(Integer, nullable=False)  # 0 = Monday ... 6 = Sunday
    start_time: Mapped[time_type] = mapped_column(Time, nullable=False)
    end_time: Mapped[time_type] = mapped_column(Time, nullable=False)
    slot_minutes: Mapped[int] = mapped_column(Integer, nullable=False)  # chosen by the doctor
    timezone: Mapped[str] = mapped_column(String(64), nullable=False)  # IANA name, e.g. Asia/Kolkata


class DoctorTimeOff(Base):
    """A date range when the doctor is unavailable (overrides weekly hours)."""

    __tablename__ = "doctor_time_off"
    __table_args__ = (CheckConstraint("start_date <= end_date", name="ck_time_off_dates"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    doctor_id: Mapped[str] = mapped_column(ForeignKey("doctors.id", ondelete="CASCADE"), index=True, nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    reason: Mapped[str | None] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class Appointment(TimestampMixin, Base):
    __tablename__ = "appointments"
    __table_args__ = (
        CheckConstraint("start_at < end_at", name="ck_appointment_times"),
        # No two active appointments for the same doctor (or the same patient) may overlap.
        ExcludeConstraint(("doctor_id", "="), (text("tstzrange(start_at, end_at, '[)')"), "&&"),
                          name="ex_appointments_doctor_overlap", using="gist", where=text(_ACTIVE_SQL)),
        ExcludeConstraint(("patient_id", "="), (text("tstzrange(start_at, end_at, '[)')"), "&&"),
                          name="ex_appointments_patient_overlap", using="gist", where=text(_ACTIVE_SQL)),
        Index("ix_appointments_doctor_start", "doctor_id", "start_at"),
        Index("ix_appointments_patient_start", "patient_id", "start_at"),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=lambda: new_id("APT"))
    patient_id: Mapped[str] = mapped_column(ForeignKey("patients.id", ondelete="RESTRICT"), nullable=False)
    doctor_id: Mapped[str] = mapped_column(ForeignKey("doctors.id", ondelete="RESTRICT"), nullable=False)
    start_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)  # stored in UTC
    end_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[AppointmentStatus] = mapped_column(
        _enum(AppointmentStatus, "appointment_status"), default=AppointmentStatus.REQUESTED, nullable=False, index=True
    )
    appointment_type: Mapped[str] = mapped_column(String(32), default="VIDEO", nullable=False)
    reason: Mapped[str | None] = mapped_column(String(500))  # patient's own words; shown only to the participants
    patient_timezone: Mapped[str | None] = mapped_column(String(64))
    created_by_user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    rescheduled_from_id: Mapped[str | None] = mapped_column(ForeignKey("appointments.id"), index=True)
    cancelled_by_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    cancel_reason: Mapped[str | None] = mapped_column(String(500))
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    patient: Mapped[Patient] = relationship(lazy="joined")
    doctor: Mapped[Doctor] = relationship(lazy="joined")


class Notification(Base):
    """In-app notification. Never contains clinical details, only a short title and a portal link."""

    __tablename__ = "notifications"
    __table_args__ = (Index("ix_notifications_user_unread", "user_id", "read_at"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    kind: Mapped[str] = mapped_column(String(40), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    body: Mapped[str | None] = mapped_column(String(500))
    link: Mapped[str | None] = mapped_column(String(300))  # path inside the authenticated portal
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


# ---------------------------------------------------------------------------
# Visit intake: symptoms and vital signs (entered by the patient, reception or the doctor)
# ---------------------------------------------------------------------------
class SymptomEntry(Base):
    """One person's description of the symptoms. Entries are never edited by someone else: the doctor's
    "additional symptoms" are a new entry. `author_role` says who wrote it (PATIENT / RECEPTION / DOCTOR)."""

    __tablename__ = "symptom_entries"
    __table_args__ = (Index("ix_symptom_entries_patient_created", "patient_id", "created_at"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    patient_id: Mapped[str] = mapped_column(ForeignKey("patients.id", ondelete="CASCADE"), nullable=False)
    appointment_id: Mapped[str | None] = mapped_column(ForeignKey("appointments.id", ondelete="SET NULL"), index=True)
    author_user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    author_role: Mapped[str] = mapped_column(String(16), nullable=False)
    text: Mapped[str] = mapped_column(String(1000), nullable=False)
    duration: Mapped[str | None] = mapped_column(String(100))
    severity: Mapped[str | None] = mapped_column(String(16))  # mild / moderate / severe
    red_flags: Mapped[str | None] = mapped_column(String(300))  # comma-separated codes from app.modules.booking.intake.RED_FLAGS
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    author: Mapped["User"] = relationship()


class VitalSigns(Base):
    """Measured at check-in (or by the doctor). Every value is optional; ranges are checked by the API."""

    __tablename__ = "vital_signs"
    __table_args__ = (Index("ix_vital_signs_patient_measured", "patient_id", "measured_at"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    patient_id: Mapped[str] = mapped_column(ForeignKey("patients.id", ondelete="CASCADE"), nullable=False)
    appointment_id: Mapped[str | None] = mapped_column(ForeignKey("appointments.id", ondelete="SET NULL"), index=True)
    recorded_by_user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    recorded_by_role: Mapped[str] = mapped_column(String(16), nullable=False)
    systolic_bp: Mapped[int | None] = mapped_column(Integer)
    diastolic_bp: Mapped[int | None] = mapped_column(Integer)
    pulse: Mapped[int | None] = mapped_column(Integer)
    temperature_c: Mapped[float | None] = mapped_column(Float)
    spo2: Mapped[int | None] = mapped_column(Integer)
    weight_kg: Mapped[float | None] = mapped_column(Float)
    height_cm: Mapped[float | None] = mapped_column(Float)
    measured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    recorded_by: Mapped["User"] = relationship()


class HealthAnswers(Base):
    """The patient's answers to the booking questions (one row per booking). Only questions a patient can answer
    without a test: tobacco, diabetes and blood-pressure medicine they were told about, chest-pain features,
    pregnancy, warning signs. Answers are "yes" / "no" / "unsure" so "not sure" is never mistaken for "no"."""

    __tablename__ = "health_answers"
    __table_args__ = (Index("ix_health_answers_patient_created", "patient_id", "created_at"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    patient_id: Mapped[str] = mapped_column(ForeignKey("patients.id", ondelete="CASCADE"), nullable=False)
    appointment_id: Mapped[str | None] = mapped_column(ForeignKey("appointments.id", ondelete="SET NULL"), unique=True)
    duration: Mapped[str] = mapped_column(String(16), nullable=False)  # code from app.modules.booking.questionnaire.DURATIONS
    severity: Mapped[str | None] = mapped_column(String(16))  # mild / moderate / severe (none for a check-up)
    red_flags: Mapped[str | None] = mapped_column(String(300))  # codes from app.modules.booking.intake.RED_FLAGS
    smoking: Mapped[str] = mapped_column(String(8), nullable=False)  # now / former / never
    diabetes: Mapped[str] = mapped_column(String(8), nullable=False)  # yes / no / unsure
    bp_medicine: Mapped[str] = mapped_column(String(8), nullable=False)
    chest_pain: Mapped[str] = mapped_column(String(8), nullable=False)  # yes / no
    cp_central: Mapped[str | None] = mapped_column(String(8))  # only when chest_pain == yes
    cp_exertion: Mapped[str | None] = mapped_column(String(8))
    cp_rest_relief: Mapped[str | None] = mapped_column(String(8))
    pregnant: Mapped[str | None] = mapped_column(String(8))  # asked only when the profile says female
    sex: Mapped[str | None] = mapped_column(String(8))  # asked only when the profile has no sex
    city: Mapped[str | None] = mapped_column(String(100))  # a name from app.modules.booking.cities, or "other"
    travel: Mapped[str | None] = mapped_column(String(8))  # travelled in the 3 weeks before booking: yes / no
    travel_city: Mapped[str | None] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class IntakeRecord(Base):
    """What the intake chat / intake form collected for one booking (fields from app.modules.booking.intake_schema),
    the symptom codes from the fixed code table, and whether a red flag was confirmed. Saved only with the patient's
    consent (consent_data_processing); shown to the appointment's doctor with the visit."""

    __tablename__ = "intake_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    patient_id: Mapped[str] = mapped_column(ForeignKey("patients.id", ondelete="CASCADE"), index=True, nullable=False)
    appointment_id: Mapped[str | None] = mapped_column(ForeignKey("appointments.id", ondelete="SET NULL"), unique=True)
    data: Mapped[dict] = mapped_column(JSON, nullable=False)
    codes: Mapped[list | None] = mapped_column(JSON)
    red_flag: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class PatientBaseline(Base):
    """The patient's own baseline answers (Phase 1 surroundings and lifestyle, consent and preferences), kept so the
    next intake doesn't ask again. Allergies, conditions, medicines, operations and family history live in
    health_history_items; date of birth and sex on patients. Updated only with consent; values are never erased."""

    __tablename__ = "patient_baselines"

    patient_id: Mapped[str] = mapped_column(ForeignKey("patients.id", ondelete="CASCADE"), primary_key=True)
    data: Mapped[dict] = mapped_column(JSON, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class LocalDiseasePattern(Base):
    """Which diseases are common in a city in certain months (e.g. Hyderabad, dengue, Aug-Nov), with its source.
    Entered by an admin (later: loaded from IDSP outbreak data). Used only as context for "conditions to consider"."""

    __tablename__ = "local_disease_patterns"
    __table_args__ = (
        CheckConstraint("start_month BETWEEN 1 AND 12 AND end_month BETWEEN 1 AND 12", name="ck_ldp_months"),
        Index("ix_local_disease_patterns_city", "city"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    city: Mapped[str] = mapped_column(String(100), nullable=False)
    disease: Mapped[str] = mapped_column(String(120), nullable=False)
    start_month: Mapped[int] = mapped_column(Integer, nullable=False)
    end_month: Mapped[int] = mapped_column(Integer, nullable=False)  # may be before start_month (wraps over the new year)
    level: Mapped[str] = mapped_column(String(8), default="HIGH", nullable=False)  # HIGH / MEDIUM
    source: Mapped[str] = mapped_column(String(200), nullable=False)
    note: Mapped[str | None] = mapped_column(String(300))
    created_by_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    def active_in(self, month: int) -> bool:
        if self.start_month <= self.end_month:
            return self.start_month <= month <= self.end_month
        return month >= self.start_month or month <= self.end_month


class HealthHistoryItem(Base):
    """Allergies, past surgeries, long-term conditions and family history, shown at the top of the doctor's view.
    kind: ALLERGY (name = substance, detail = reaction), SURGERY (detail = year), CONDITION, FAMILY (detail = relative),
    or NO_KNOWN_ALLERGIES (an explicit "asked, none"; different from "never asked").
    Items are never deleted: removing one sets removed_at, so the history stays visible to audits."""

    __tablename__ = "health_history_items"
    __table_args__ = (Index("ix_health_history_patient_kind", "patient_id", "kind"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    patient_id: Mapped[str] = mapped_column(ForeignKey("patients.id", ondelete="CASCADE"), nullable=False)
    kind: Mapped[str] = mapped_column(String(24), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    detail: Mapped[str | None] = mapped_column(String(300))
    added_by_user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    added_by_role: Mapped[str] = mapped_column(String(16), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    removed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    removed_by_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))

    added_by: Mapped["User"] = relationship(foreign_keys=[added_by_user_id])


# Doctor applications and one-time links live in their own module (registered here so Alembic sees them).
from app.models.doctor_onboarding import ApplicationDocument, DoctorApplication, OneTimeLink  # noqa: E402,F401
