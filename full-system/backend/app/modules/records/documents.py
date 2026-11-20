"""Document upload pipeline.

UPLOAD -> AUTHORIZE -> VALIDATE -> (PDF) EXTRACT TEXT WITH PYMUPDF -> STORE
       -> DB METADATA -> CLEAN -> CHUNK -> EMBED -> CHROMA (+ metadata)

Upload authorization (enforced here, never in the frontend):
  PATIENT: may only upload MEDICAL documents to their own patient id.
  DOCTOR : may upload MEDICAL documents only for a patient for whom
           PREVIOUS_VISIT = TRUE AND PATIENT_AUTHORIZATION = TRUE
           (resolve_patient_context -> check_doctor_patient_access).
  ADMIN  : may upload ADMINISTRATIVE documents (no patient). May upload a
           patient document ONLY with the explicit `can_manage_patient_documents`
           permission AND a written justification; logged as ADMIN_OPERATION.
"""

import hashlib
import logging
import uuid
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone

from fastapi import Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.ai import vector_store
from app.modules.ai.embeddings import EmbeddingError
from app.core.config import get_settings
from app.core.errors import AppError
from app.models import (
    Consultation, Diagnosis, Document, DocumentCategory, MedicalRecord, Patient, Prescription, RecordType, Role, User,
)
from app.shared.access_control import resolve_patient_context
from app.shared.audit import Action, Result, audit
from app.modules.records import medical_check
from app.shared.document_processing import chunk_text, extract_pdf_text, validate_upload
from app.shared.storage import get_storage

log = logging.getLogger("ddht.documents")


@dataclass
class UploadRequest:
    data: bytes
    filename: str | None
    content_type: str | None
    patient_id: str | None
    record_id: str | None
    document_type: str
    document_date: date | None
    title: str | None
    description: str | None
    category: str = "MEDICAL"
    admin_reason: str | None = None
    document_id: str | None = None  # fixed ids for seed data only; never set from the API


def _reject(user: User, reason: str, patient_id: str | None, request: Request | None, db: Session) -> None:
    audit(Action.DOCUMENT_UPLOAD_REJECTED, Result.DENIED, user=user,
          patient_id=patient_id if patient_id and db.get(Patient, patient_id) else None,
          resource_type="document", reason=reason, request=request)


def _authorize_upload(db: Session, user: User, req: UploadRequest, request: Request | None) -> str | None:
    """Returns the patient_id the document will be attached to (None for admin docs)."""
    try:
        category = DocumentCategory(req.category)
    except ValueError:
        raise AppError(422, "INVALID_CATEGORY", "Invalid document category.")

    if user.role == Role.PATIENT:
        own = user.patient.id
        target = req.patient_id or own
        if target != own:
            reason = "Patients can only upload documents to their own medical record."
            _reject(user, reason, target, request, db)
            raise AppError(403, "UPLOAD_FORBIDDEN", reason)
        if category != DocumentCategory.MEDICAL:
            raise AppError(403, "UPLOAD_FORBIDDEN", "Patients can only upload medical documents.")
        return own

    if user.role == Role.DOCTOR:
        if not req.patient_id:
            raise AppError(422, "PATIENT_REQUIRED", "Select the patient this document belongs to.")
        if category != DocumentCategory.MEDICAL:
            raise AppError(403, "UPLOAD_FORBIDDEN", "Doctors can only upload patient medical documents.")
        try:
            resolve_patient_context(db, user, req.patient_id, "document_upload", request)
        except AppError as exc:
            _reject(user, exc.extra.get("reason") or exc.message, req.patient_id, request, db)
            raise
        return req.patient_id

    if user.role == Role.ADMIN:
        if category == DocumentCategory.ADMINISTRATIVE:
            if req.patient_id:
                raise AppError(422, "INVALID_CATEGORY",
                               "Administrative documents cannot be attached to a patient. Use category MEDICAL.")
            return None
        # Patient medical document uploaded by an admin: explicit permission + justification.
        if not req.patient_id:
            raise AppError(422, "PATIENT_REQUIRED", "Select the patient this document belongs to.")
        if not (user.admin and user.admin.can_manage_patient_documents):
            reason = "This administrator does not have permission to manage patient documents."
            _reject(user, reason, req.patient_id, request, db)
            raise AppError(403, "UPLOAD_FORBIDDEN", reason)
        if not req.admin_reason or len(req.admin_reason.strip()) < 10:
            raise AppError(422, "ADMIN_REASON_REQUIRED",
                           "A justification (at least 10 characters) is required for administrative uploads of patient documents.")
        resolve_patient_context(db, user, req.patient_id, "admin_document_upload", request,
                                allowed_roles=(Role.ADMIN,))
        return req.patient_id

    raise AppError(403, "FORBIDDEN_ROLE", "Your role is not permitted to upload documents.")


def upload_document(db: Session, user: User, req: UploadRequest, request: Request | None = None) -> Document:
    settings = get_settings()
    patient_id = _authorize_upload(db, user, req, request)

    try:
        doc_type = RecordType(req.document_type)
    except ValueError:
        raise AppError(422, "INVALID_DOCUMENT_TYPE", "Invalid document / record type.")

    record: MedicalRecord | None = None
    if req.record_id:
        record = db.get(MedicalRecord, req.record_id)
        if record is None or record.patient_id != patient_id:
            raise AppError(404, "RECORD_NOT_FOUND", "Medical record not found for this patient.")

    # --- VALIDATE ---------------------------------------------------------
    try:
        valid = validate_upload(req.filename, req.content_type, req.data, settings.max_upload_bytes)
        extraction = extract_pdf_text(req.data) if valid.extension == ".pdf" else None
        verdict = None
        if user.role == Role.PATIENT:  # patients may upload medical documents only (doctors and admins are trusted)
            verdict = medical_check.check(req.data, valid.extension, extraction.text if extraction else None)
            if verdict.status == "NOT_MEDICAL":
                raise AppError(422, "NOT_A_MEDICAL_DOCUMENT",
                               f"{verdict.reason} Please upload a medical file: a lab or test report, prescription, "
                               "discharge summary, scan report or medical certificate.")
    except AppError as exc:
        _reject(user, exc.message, patient_id, request, db)
        raise

    # --- STORE (safe server-generated name; user filename never used) ----
    safe_name = f"{uuid.uuid4().hex}{valid.extension}"
    folder = f"patients/{patient_id}" if patient_id else "admin"
    key = f"{folder}/{safe_name}"
    try:
        get_storage().save(key, req.data)
    except Exception:
        raise AppError(500, "UPLOAD_STORAGE_FAILED", "The file could not be stored. Please try again.")

    title = (req.title or "").strip() or valid.display_name.rsplit(".", 1)[0]
    category = DocumentCategory(req.category)

    # --- DB: record + document -----------------------------------------
    if record is None and category == DocumentCategory.MEDICAL:
        record = MedicalRecord(
            patient_id=patient_id,
            doctor_id=user.doctor.id if user.role == Role.DOCTOR else None,
            hospital_id=user.doctor.hospital_id if user.role == Role.DOCTOR else None,
            record_type=doc_type,
            title=title[:250],
            record_date=req.document_date or date.today(),
            description=req.description,
            status="ACTIVE",
            created_by_user_id=user.id,
        )
        db.add(record)
        db.flush()

    doc = Document(
        **({"id": req.document_id} if req.document_id else {}),
        patient_id=patient_id,
        record_id=record.id if record else None,
        uploaded_by=user.id,
        uploader_role=user.role,
        category=category,
        title=title[:250],
        original_filename=valid.display_name,
        filename=safe_name,
        storage_path=key,
        mime_type=valid.mime_type,
        size_bytes=len(req.data),
        sha256=hashlib.sha256(req.data).hexdigest(),
        document_type=doc_type,
        document_date=req.document_date,
        description=req.description,
        admin_reason=req.admin_reason.strip() if user.role == Role.ADMIN and req.admin_reason else None,
        content_check=None if verdict is None else ("MEDICAL" if verdict.status == "MEDICAL" else "NOT_CHECKED"),
        content_check_note=verdict.reason[:300] if verdict else None,
    )
    if extraction is None:
        doc.extraction_status = "NOT_APPLICABLE"
        doc.index_status = "SKIPPED"
        doc.processing_status = "PROCESSED_WITH_WARNINGS"
        doc.processing_message = ("Image stored. Text extraction (OCR) is not supported for images, "
                                  "so this file is not searchable by the AI assistant.")
    else:
        doc.page_count = extraction.page_count
        doc.extraction_status = extraction.status
        doc.extracted_text = extraction.text or None
        doc.processing_message = extraction.message
    db.add(doc)
    db.commit()
    db.refresh(doc)

    # --- CHUNK -> EMBED -> CHROMA -------------------------------------
    if extraction is not None and doc.patient_id:
        index_document(db, doc)
    elif extraction is not None:
        # Administrative documents are never placed in the patient vector index.
        doc.index_status = "SKIPPED"
        doc.processing_status = "PROCESSED" if extraction.status == "EXTRACTED" else "PROCESSED_WITH_WARNINGS"
        db.commit()

    audit(Action.DOCUMENT_UPLOADED, Result.SUCCESS, user=user, patient_id=patient_id,
          resource_type="document", resource_id=doc.id,
          reason=f"type={doc_type.value}; category={category.value}; status={doc.processing_status}", request=request)
    if user.role == Role.ADMIN:
        audit(Action.ADMIN_OPERATION, Result.SUCCESS, user=user, patient_id=patient_id,
              resource_type="document_upload", resource_id=doc.id,
              reason=f"Admin upload ({category.value}). Justification: {doc.admin_reason or 'n/a'}", request=request)
    return doc


def index_document(db: Session, doc: Document) -> None:
    """Chunk + embed + store in Chroma. Failures are recorded, never raised."""
    chunks = chunk_text(doc.extracted_text or "")
    if not chunks:
        doc.index_status = "SKIPPED"
        doc.chunk_count = 0
        doc.processing_status = "PROCESSED_WITH_WARNINGS"
        db.commit()
        return
    try:
        n = vector_store.index_chunks(
            patient_id=doc.patient_id,
            document_id=doc.id,
            record_id=doc.record_id,
            record_type=doc.document_type.value,
            date=(doc.document_date or doc.upload_date.date()).isoformat(),
            title=doc.title,
            chunks=chunks,
        )
        doc.chunk_count = n
        doc.index_status = "INDEXED"
        doc.processing_status = "PROCESSED" if doc.extraction_status == "EXTRACTED" else "PROCESSED_WITH_WARNINGS"
    except EmbeddingError as exc:
        doc.index_status = "FAILED"
        doc.processing_status = "PROCESSED_WITH_WARNINGS"
        doc.processing_message = f"Text extracted and stored, but embeddings could not be generated ({exc}). The document can be re-indexed later."
    except vector_store.VectorStoreError as exc:
        doc.index_status = "FAILED"
        doc.processing_status = "PROCESSED_WITH_WARNINGS"
        doc.processing_message = f"Text extracted and stored, but the vector database failed ({exc}). The document can be re-indexed later."
    db.commit()


# ---------------------------------------------------------------------------
# Deleting an upload (undo a mistake)
# ---------------------------------------------------------------------------
# Records are otherwise never deleted. The only exceptions:
#   * the person who uploaded a document may delete it within UPLOAD_UNDO_DAYS
#     (wrong file, someone else's report, duplicate). A doctor must still have
#     access to the patient (the patient's consent).
#   * an administrator may delete any upload at any time, with a written reason.
# Deletion removes the stored file, its extracted text and its search vectors.
# The audit log keeps a DOCUMENT_DELETED entry (metadata only, never content).


def deletable_until(doc: Document) -> datetime:
    return doc.upload_date + timedelta(days=get_settings().upload_undo_days)


def delete_document(db: Session, user: User, document_id: str, reason: str | None,
                    request: Request | None = None) -> dict:
    doc = db.get(Document, document_id)
    if doc is None:
        raise AppError(404, "DOCUMENT_NOT_FOUND", "Document not found.")
    days = get_settings().upload_undo_days
    reason = (reason or "").strip()

    if user.role == Role.ADMIN:
        if len(reason) < 10:
            raise AppError(422, "ADMIN_REASON_REQUIRED",
                           "A reason (at least 10 characters) is required when an administrator deletes a document.")
    else:
        if doc.uploaded_by != user.id:
            _deny_delete(user, doc, "Only the person who uploaded a document can delete it.", request)
            raise AppError(403, "DELETE_FORBIDDEN",
                           "You can only delete documents you uploaded yourself. "
                           "You can restrict this record instead (hides it from doctors and the AI), or ask an administrator to remove it.")
        if datetime.now(timezone.utc) > deletable_until(doc):
            _deny_delete(user, doc, f"Delete window ({days} days) has passed.", request)
            raise AppError(403, "DELETE_WINDOW_EXPIRED",
                           f"Uploads can only be deleted within {days} days. You can restrict this record "
                           "instead, or ask an administrator to remove it.")
        if user.role == Role.DOCTOR:
            # Same rule as viewing/uploading: the patient's current consent.
            resolve_patient_context(db, user, doc.patient_id, "document_delete", request, log_grant=False)
        elif user.role == Role.PATIENT and doc.patient_id != user.patient.id:
            raise AppError(403, "DELETE_FORBIDDEN", "You can only delete your own documents.")

    summary = {"document_id": doc.id, "title": doc.title, "filename": doc.original_filename,
               "patient_id": doc.patient_id, "record_removed": None}
    storage_key = doc.storage_path

    # Remove the record too if it only existed because of this upload.
    record = db.get(MedicalRecord, doc.record_id) if doc.record_id else None
    if record is not None:
        other_docs = db.scalar(select(func.count()).select_from(Document)
                               .where(Document.record_id == record.id, Document.id != doc.id)) or 0
        linked = sum(db.scalar(select(func.count()).select_from(m).where(m.record_id == record.id)) or 0
                     for m in (Diagnosis, Prescription, Consultation))
        if other_docs == 0 and linked == 0 and record.created_by_user_id == doc.uploaded_by:
            summary["record_removed"] = record.id
        else:
            record = None

    db.delete(doc)
    db.flush()
    if record is not None:
        db.delete(record)
    db.commit()

    # Best-effort clean-up of the file and search vectors (the DB is the source of truth;
    # a leftover vector can no longer be returned because retrieval re-checks the DB).
    try:
        get_storage().delete(storage_key)
    except Exception:
        log.exception("Could not delete stored file %s", storage_key)
    try:
        vector_store.delete_document(summary["document_id"])
    except Exception:
        log.exception("Could not delete vectors for %s", summary["document_id"])

    note = (f"title='{summary['title']}'; file='{summary['filename']}'"
            + (f"; record {summary['record_removed']} removed" if summary["record_removed"] else "")
            + (f"; reason: {reason}" if reason else ""))
    audit(Action.DOCUMENT_DELETED, Result.SUCCESS, user=user, patient_id=summary["patient_id"],
          resource_type="document", resource_id=summary["document_id"], reason=note, request=request)
    if user.role == Role.ADMIN:
        audit(Action.ADMIN_OPERATION, Result.SUCCESS, user=user, patient_id=summary["patient_id"],
              resource_type="document_delete", resource_id=summary["document_id"], reason=note, request=request)
    return summary


def _deny_delete(user: User, doc: Document, reason: str, request: Request | None) -> None:
    audit(Action.DOCUMENT_DELETED, Result.DENIED, user=user, patient_id=doc.patient_id,
          resource_type="document", resource_id=doc.id, reason=reason, request=request)
