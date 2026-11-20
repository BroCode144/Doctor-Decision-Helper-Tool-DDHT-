"""Doctor applications (sign-up with documents, checked, then approved by an admin) and one-time links.

Kept in its own module; app/models/__init__.py imports it at the end so the tables are registered.
No doctor account exists until an admin approves the application: then a User + Doctor (VERIFIED) are created
and the doctor gets an email with a one-time "set your password" link (valid 48 hours).
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _ref() -> str:
    return "DR-" + uuid.uuid4().hex[:8].upper()


class ApplicationStatus:
    CHECKING = "CHECKING"  # documents are being read and checked (automatic, a minute or two)
    UNDER_REVIEW = "UNDER_REVIEW"  # waiting for an admin
    NEEDS_INFO = "NEEDS_INFO"  # the doctor must re-upload something (asked by the check or by an admin)
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    ALL = (CHECKING, UNDER_REVIEW, NEEDS_INFO, APPROVED, REJECTED)


class DoctorApplication(Base):
    __tablename__ = "doctor_applications"
    __table_args__ = (Index("ix_doctor_applications_status_created", "status", "created_at"),)

    id: Mapped[str] = mapped_column(String(16), primary_key=True, default=_ref)  # also the reference shown to the doctor
    full_name: Mapped[str] = mapped_column(String(200), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    phone: Mapped[str | None] = mapped_column(String(32))
    specialization: Mapped[str] = mapped_column(String(120), nullable=False)
    qualification: Mapped[str] = mapped_column(String(120), nullable=False)  # e.g. "MBBS, MD (Medicine)"
    council: Mapped[str] = mapped_column(String(16), nullable=False)  # code from app.modules.doctors.councils
    registration_number: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    registration_year: Mapped[int] = mapped_column(Integer, nullable=False)
    claims_specialist: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)  # then a PG degree is required
    hospital_id: Mapped[str | None] = mapped_column(ForeignKey("hospitals.id", ondelete="SET NULL"))
    status: Mapped[str] = mapped_column(String(16), default=ApplicationStatus.CHECKING, nullable=False)
    check_summary: Mapped[str | None] = mapped_column(Text)  # JSON: the automatic checklist
    info_request: Mapped[str | None] = mapped_column(Text)  # JSON: {"kinds": [...], "message": "..."} when NEEDS_INFO
    decision_note: Mapped[str | None] = mapped_column(Text)  # rejection reason / admin note
    reviewed_by_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))  # set on approval
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now, nullable=False)

    documents: Mapped[list["ApplicationDocument"]] = relationship(back_populates="application", order_by="ApplicationDocument.id")


class ApplicationDocument(Base):
    """One uploaded file. A re-upload adds a new row and marks the older one of the same kind superseded."""

    __tablename__ = "application_documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    application_id: Mapped[str] = mapped_column(ForeignKey("doctor_applications.id", ondelete="CASCADE"), index=True, nullable=False)
    kind: Mapped[str] = mapped_column(String(16), nullable=False)  # REGISTRATION / DEGREE / PHOTO_ID / PG_DEGREE / HOSPITAL_LETTER
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    storage_path: Mapped[str | None] = mapped_column(String(500))  # None once deleted (photo ID after the decision)
    mime_type: Mapped[str] = mapped_column(String(64), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    read_method: Mapped[str | None] = mapped_column(String(40))  # "pdf text" / "local Qwen2.5-VL" / "not read"
    read_text: Mapped[str | None] = mapped_column(Text)  # never stored for the photo ID
    check_result: Mapped[str | None] = mapped_column(Text)  # JSON: the checks for this file
    superseded: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False)

    application: Mapped[DoctorApplication] = relationship(back_populates="documents")


class OneTimeLink(Base):
    """A one-time emailed link: SET_PASSWORD (after approval, 48 h) or REUPLOAD (when more documents are needed).
    Only a hash of the token is stored."""

    __tablename__ = "one_time_links"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    purpose: Mapped[str] = mapped_column(String(16), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    application_id: Mapped[str | None] = mapped_column(ForeignKey("doctor_applications.id", ondelete="CASCADE"))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False)
