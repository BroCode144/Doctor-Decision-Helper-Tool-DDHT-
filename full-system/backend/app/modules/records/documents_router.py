
from datetime import date

from fastapi.concurrency import run_in_threadpool
from fastapi import APIRouter, Depends, File, Form, Query, Request, UploadFile
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.core.config import get_settings
from app.core.errors import AppError
from app.db.session import get_db
from app.models import Document, DocumentCategory, Role, User
from app.modules.records import patient_data as pdata
from app.shared.access_control import resolve_patient_context
from app.shared.audit import Action, Result, audit
from app.modules.records.documents import UploadRequest, delete_document, index_document, upload_document
from app.shared.storage import StorageError, get_storage

router = APIRouter(prefix="/documents", tags=["documents"])


@router.post("/upload", status_code=201)
async def upload(
    request: Request,
    file: UploadFile = File(...),
    document_type: str = Form(...),
    patient_id: str | None = Form(None),
    record_id: str | None = Form(None),
    document_date: date | None = Form(None),
    title: str | None = Form(None, max_length=250),
    description: str | None = Form(None, max_length=5000),
    category: str = Form("MEDICAL"),
    admin_reason: str | None = Form(None, max_length=1000),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    max_bytes = get_settings().max_upload_bytes
    data = await file.read(max_bytes + 1)  # never buffer more than the limit + 1 byte
    req = UploadRequest(
        data=data, filename=file.filename, content_type=file.content_type,
        patient_id=(patient_id or None), record_id=(record_id or None), document_type=document_type,
        document_date=document_date, title=title, description=description,
        category=category, admin_reason=admin_reason,
    )
    # in a worker thread: reading a photo with the local model takes seconds and must not block other requests
    doc = await run_in_threadpool(upload_document, db, user, req, request)
    return {"document": pdata.serialize_document(doc), "message": doc.processing_message or "Document uploaded and processed."}


def _authorize_document(db: Session, user: User, doc_id: str, request: Request, *, content: bool) -> Document:
    doc = db.get(Document, doc_id)
    if doc is None:
        raise AppError(404, "DOCUMENT_NOT_FOUND", "Document not found.")
    if doc.category == DocumentCategory.ADMINISTRATIVE:
        if user.role != Role.ADMIN:
            raise AppError(403, "FORBIDDEN", "Only administrators can access administrative documents.")
        return doc
    if user.role == Role.ADMIN:
        if content:
            audit(Action.ACCESS_DENIED, Result.DENIED, user=user, patient_id=doc.patient_id,
                  resource_type="document_content", resource_id=doc.id,
                  reason="Administrators cannot view patient medical document contents.", request=request)
            raise AppError(403, "FORBIDDEN_ROLE", "Administrators cannot view patient medical document contents.")
        return doc  # metadata only
    ctx = resolve_patient_context(db, user, doc.patient_id, "document_view", request, log_grant=False)
    visible = pdata.get_visible_document(db, ctx, doc.id)
    if visible is None:
        raise AppError(404, "DOCUMENT_NOT_FOUND", "Document not found.")
    return visible


@router.get("")
def list_documents(request: Request, patient_id: str | None = Query(None),
                   user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if user.role == Role.ADMIN:
        raise AppError(403, "FORBIDDEN_ROLE", "Administrators should use /admin/uploads.")
    if user.role == Role.PATIENT:
        patient_id = patient_id or user.patient.id
    if not patient_id:
        raise AppError(422, "PATIENT_REQUIRED", "patient_id is required.")
    ctx = resolve_patient_context(db, user, patient_id, "documents", request)
    return [pdata.serialize_document(d) for d in pdata.list_documents(db, ctx)]


@router.get("/{document_id}")
def get_document(document_id: str, request: Request, include_text: bool = False,
                 user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    doc = _authorize_document(db, user, document_id, request, content=include_text)
    audit(Action.DOCUMENT_VIEWED, Result.SUCCESS, user=user, patient_id=doc.patient_id,
          resource_type="document" if include_text else "document_metadata", resource_id=doc.id, request=request)
    return pdata.serialize_document(doc, include_text=include_text)


@router.get("/{document_id}/download")
def download_document(document_id: str, request: Request,
                      user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    doc = _authorize_document(db, user, document_id, request, content=True)
    try:
        data = get_storage().read(doc.storage_path)
    except StorageError:
        raise AppError(404, "FILE_MISSING", "The stored file could not be found.")
    audit(Action.DOCUMENT_VIEWED, Result.SUCCESS, user=user, patient_id=doc.patient_id,
          resource_type="document_file", resource_id=doc.id, request=request)
    safe = doc.original_filename.encode("ascii", "ignore").decode().replace('"', "") or doc.filename
    return Response(
        content=data,
        media_type=doc.mime_type,
        headers={
            "Content-Disposition": f'inline; filename="{safe}"',
            "X-Content-Type-Options": "nosniff",
            "Content-Security-Policy": "default-src 'none'; sandbox",
            "Cache-Control": "no-store",
        },
    )


@router.delete("/{document_id}")
def delete(document_id: str, request: Request, reason: str | None = Query(None, max_length=500),
           user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Delete an upload. Uploader: own uploads within UPLOAD_UNDO_DAYS. Admin: any, with a reason."""
    summary = delete_document(db, user, document_id, reason, request)
    msg = "Document deleted."
    if summary["record_removed"]:
        msg = "Document and its record deleted."
    return {**summary, "message": msg}


@router.post("/{document_id}/reindex")
def reindex(document_id: str, request: Request,
            user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    doc = db.get(Document, document_id)
    if doc is None:
        raise AppError(404, "DOCUMENT_NOT_FOUND", "Document not found.")
    if doc.category != DocumentCategory.MEDICAL or not doc.extracted_text:
        raise AppError(422, "NOT_INDEXABLE", "This document has no extracted text to index.")
    if user.role != Role.ADMIN:
        _authorize_document(db, user, document_id, request, content=True)
    index_document(db, doc)
    db.refresh(doc)
    if user.role == Role.ADMIN:
        audit(Action.ADMIN_OPERATION, Result.SUCCESS, user=user, patient_id=doc.patient_id,
              resource_type="document_reindex", resource_id=doc.id, request=request)
    return pdata.serialize_document(doc)
