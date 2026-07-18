"""
POST /upload          — single file upload
POST /upload/bulk     — multiple file upload
GET  /documents       — list all documents
GET  /documents/{id}  — get document + status
DELETE /documents/{id}
"""
import os
import shutil
import uuid
from datetime import datetime
from pathlib import Path
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, BackgroundTasks, Request

from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Document, DocumentStatus, User
from app.config.settings import get_settings
from app.services.extractor import extract_text
from app.services.chunker import chunk_document
from app.dependencies.rbac import require_manager_or_above, require_admin
from app.services.limiter import limiter
from app.services.auth import get_current_user
from app.services.audit import log_action

settings = get_settings()

router = APIRouter(prefix="/api", tags=["documents"])

UPLOAD_DIR = Path(settings.upload_dir)
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


def _validate_file(file: UploadFile):
    filename = file.filename or ""
    if ".." in filename or "/" in filename or "\\" in filename:
        raise HTTPException(
            status_code=400,
            detail="Path traversal attempt detected in filename",
        )
    ext = Path(filename).suffix.lstrip(".").lower()
    if ext not in settings.allowed_extensions_list:
        raise HTTPException(
            status_code=400,
            detail=f"File type '.{ext}' not allowed. Allowed: {settings.allowed_extensions_list}",
        )
    return ext



def _save_file(file: UploadFile, ext: str) -> tuple[str, str, int]:
    """Save uploaded file to disk. Returns (saved_filename, file_path, size)."""
    saved_name = f"{uuid.uuid4().hex}.{ext}"
    dest = UPLOAD_DIR / saved_name
    with dest.open("wb") as f:
        shutil.copyfileobj(file.file, f)
    size = dest.stat().st_size
    return saved_name, str(dest), size


def _run_extraction(doc_id: int, db: Session):
    doc = db.query(Document).filter(Document.id == doc_id).first()
    if not doc:
        return
    try:
        doc.status = DocumentStatus.extracting
        db.commit()
        text, pages = extract_text(doc.file_path, doc.file_type)
        doc.extracted_text = text
        doc.page_count = pages
        doc.status = DocumentStatus.extracted
        doc.processed_at = datetime.utcnow()
        # Immediately chunk after successful extraction
        chunk_document(doc, db)
        # Immediately embed after successful chunking
        from app.services.embedder import embed_document
        embed_document(doc, db)
    except Exception as e:
        doc.status = DocumentStatus.failed
        doc.extraction_error = str(e)
    finally:
        db.commit()


@router.post("/upload", status_code=201, dependencies=[Depends(require_manager_or_above)])
@limiter.limit(settings.rate_limit_upload)
def upload_file(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    department: str | None = None,
    request: Request = None,
    db: Session = Depends(get_db),
):
    ext = _validate_file(file)
    saved_name, file_path, size = _save_file(file, ext)

    doc = Document(
        filename=saved_name,
        original_filename=file.filename,
        file_path=file_path,
        file_type=ext,
        file_size=size,
        department=department,
        source="manual",
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)

    background_tasks.add_task(_run_extraction, doc.id, db)

    log_action(
        db,
        action="upload",
        user_id=None,
        ip_address=request.client.host if request and request.client else None,
        details={"filename": file.filename, "document_id": doc.id},
    )

    return {"id": doc.id, "filename": doc.original_filename, "status": doc.status}



@router.post("/upload/bulk", status_code=201, dependencies=[Depends(require_manager_or_above)])
@limiter.limit(settings.rate_limit_upload)
def upload_bulk(

    background_tasks: BackgroundTasks,
    files: list[UploadFile] = File(...),
    department: str | None = None,
    request: Request = None,
    db: Session = Depends(get_db),
):

    results = []
    for file in files:
        try:
            ext = _validate_file(file)
            saved_name, file_path, size = _save_file(file, ext)
            doc = Document(
                filename=saved_name,
                original_filename=file.filename,
                file_path=file_path,
                file_type=ext,
                file_size=size,
                department=department,
                source="manual",
            )
            db.add(doc)
            db.commit()
            db.refresh(doc)
            background_tasks.add_task(_run_extraction, doc.id, db)
            results.append({"id": doc.id, "filename": file.filename, "status": "queued"})
        except HTTPException as e:
            results.append({"filename": file.filename, "error": e.detail})
            continue

        log_action(
            db,
            action="upload",
            user_id=None,
            ip_address=request.client.host if request and request.client else None,
            details={"filename": file.filename, "document_id": doc.id},
        )

    return {"uploaded": len(results), "results": results}



@router.get("/documents")
def list_documents(
    status: str | None = None,
    department: str | None = None,
    db: Session = Depends(get_db),
):
    q = db.query(Document)
    if status:
        q = q.filter(Document.status == status)
    if department:
        q = q.filter(Document.department == department)
    docs = q.order_by(Document.uploaded_at.desc()).all()
    return [
        {
            "id": d.id,
            "filename": d.original_filename,
            "file_type": d.file_type,
            "file_size": d.file_size,
            "department": d.department,
            "status": d.status,
            "page_count": d.page_count,
            "chunk_count": len(d.chunks) if getattr(d, "chunks", None) is not None else None,
            "uploaded_at": d.uploaded_at,
            "processed_at": d.processed_at,
            "extraction_error": d.extraction_error,
        }
        for d in docs
    ]


@router.get("/documents/{doc_id}")
def get_document(doc_id: int, db: Session = Depends(get_db)):
    doc = db.query(Document).filter(Document.id == doc_id).first()
    if not doc:
        raise HTTPException(404, "Document not found")
    return {
        "id": doc.id,
        "filename": doc.original_filename,
        "file_type": doc.file_type,
        "file_size": doc.file_size,
        "department": doc.department,
        "access_level": doc.access_level,
        "status": doc.status,
        "page_count": doc.page_count,
        "extraction_error": doc.extraction_error,
        "uploaded_at": doc.uploaded_at,
        "processed_at": doc.processed_at,
        "chunk_count": len(doc.chunks),
    }


@router.delete("/documents/{doc_id}", status_code=204, dependencies=[Depends(require_admin)])
def delete_document(doc_id: int, db: Session = Depends(get_db)):
    doc = db.query(Document).filter(Document.id == doc_id).first()
    if not doc:
        raise HTTPException(404, "Document not found")
    # Delete from disk
    file_path = doc.file_path
    if not os.path.isabs(file_path):
        backend_dir = Path(__file__).parent.parent.parent.resolve()
        file_path = str((backend_dir / file_path).resolve())
    if os.path.exists(file_path):
        os.remove(file_path)
    db.delete(doc)
    db.commit()



@router.get("/documents/{doc_id}/download")
def secure_download(
    doc_id: int,
    current_user: "User" = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    from fastapi.responses import FileResponse
    from app.models import User, AccessLevel

    doc = db.query(Document).filter(Document.id == doc_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    # Access control checks
    role = str(current_user.role).strip().lower()
    
    # 1. Access Level constraints
    if doc.access_level == AccessLevel.confidential:
        if role not in ("admin", "hr", "manager"):
            raise HTTPException(status_code=403, detail="Forbidden: Confidential document")
    elif doc.access_level == AccessLevel.restricted:
        if role not in ("admin", "hr") and doc.owner_user_id != current_user.id:
            raise HTTPException(status_code=403, detail="Forbidden: Restricted document")
            
    # 2. Department constraints (non-admin/non-hr users must match department if doc is department-restricted)
    if doc.department and role not in ("admin", "hr"):
        user_dept = (current_user.department or "").strip().lower()
        doc_dept = doc.department.strip().lower()
        if user_dept != doc_dept:
            raise HTTPException(status_code=403, detail=f"Forbidden: Document is restricted to {doc.department} department")

    # Resolve file path
    file_path = doc.file_path
    if not os.path.isabs(file_path):
        backend_dir = Path(__file__).parent.parent.parent.resolve()
        file_path = str((backend_dir / file_path).resolve())

    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found on disk")

    return FileResponse(
        file_path,
        media_type="application/octet-stream",
        filename=doc.original_filename
    )
