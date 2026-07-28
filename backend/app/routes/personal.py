"""
Personal document uploads - private to the uploading user's own chat only.
Unlike /api/upload, any authenticated user (not just manager+) can use this.
"""
import uuid
import shutil
from pathlib import Path
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, BackgroundTasks
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Document, User
from app.config.settings import get_settings
from app.services.auth import get_current_user
from app.routes.upload import _validate_file, _save_file, _run_extraction

settings = get_settings()
router = APIRouter(prefix="/api/personal", tags=["personal"])


@router.post("/upload", status_code=201)
def upload_personal_file(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    ext = _validate_file(file)
    saved_name, file_path, size, actual_ext = _save_file(file, ext)

    doc = Document(
        filename=saved_name,
        original_filename=file.filename,
        file_path=file_path,
        file_type=actual_ext,
        file_size=size,
        department=None,
        source="personal",
        owner_user_id=current_user.id,
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)

    background_tasks.add_task(_run_extraction, doc.id)

    return {"id": doc.id, "filename": doc.original_filename, "status": doc.status}


@router.get("/documents/{doc_id}/status")
def get_personal_document_status(
    doc_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    doc = db.query(Document).filter(Document.id == doc_id).first()
    if not doc:
        raise HTTPException(404, "Document not found")
    if doc.owner_user_id != current_user.id:
        raise HTTPException(403, "Not your document")
    return {
        "id": doc.id,
        "filename": doc.original_filename,
        "status": doc.status,
        "extraction_error": doc.extraction_error,
    }


@router.get("/documents")
def list_my_personal_documents(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    docs = (
        db.query(Document)
        .filter(Document.owner_user_id == current_user.id)
        .order_by(Document.uploaded_at.desc())
        .all()
    )
    return [
        {
            "id": d.id,
            "filename": d.original_filename,
            "file_type": d.file_type,
            "status": d.status,
            "source": d.source,
            "uploaded_at": d.uploaded_at,
        }
        for d in docs
    ]


@router.delete("/documents/{doc_id}", status_code=204)
def delete_my_personal_document(
    doc_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    doc = db.query(Document).filter(Document.id == doc_id).first()
    if not doc:
        raise HTTPException(404, "Document not found")
    if doc.owner_user_id != current_user.id:
        raise HTTPException(403, "You can only delete your own personal documents")
    import os
    if os.path.exists(doc.file_path):
        os.remove(doc.file_path)
    db.delete(doc)
    db.commit()
