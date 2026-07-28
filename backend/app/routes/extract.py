import io
import os
import uuid
from pathlib import Path
from fastapi import APIRouter, UploadFile, File, HTTPException, BackgroundTasks, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.config.settings import get_settings
from app.database import get_db
from app.models import Document, DocumentStatus, User
from app.services.auth import get_current_user
from app.services.extractor import extract_text as service_extract_text

settings = get_settings()
router = APIRouter(prefix="/api", tags=["extract"])
UPLOAD_DIR = Path(settings.upload_dir)


def _run_chunking_and_embedding(doc_id: int):
    from app.database import SessionLocal
    from app.services.process_all import process_single_document_by_id
    try:
        process_single_document_by_id(doc_id)
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"Failed background chunk/embed for personal doc {doc_id}: {e}")


@router.post("/extract-text")
async def extract_text(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    name = (file.filename or "").lower()
    ext = Path(name).suffix.lstrip(".").lower()
    if not ext:
        ext = "txt"
        
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    saved_name = f"personal_{uuid.uuid4().hex}.{ext}"
    dest = UPLOAD_DIR / saved_name
    
    file_saved = False
    try:
        with dest.open("wb") as f:
            content = await file.read()
            f.write(content)
        file_saved = True
        
        text, _ = service_extract_text(str(dest), ext)
    except Exception as e:
        if dest.exists():
            try:
                os.remove(dest)
            except Exception:
                pass
        raise HTTPException(500, f"Extraction failed: {e}")
        
    if not text or not text.strip():
        if dest.exists():
            try:
                os.remove(dest)
            except Exception:
                pass
        raise HTTPException(400, f"Could not extract any text from this file type (.{ext}).")
        
    try:
        from app.services.versioning import handle_document_versioning
        version = handle_document_versioning(db, file.filename or "", current_user.id)
        
        # Create personal document record
        doc = Document(
            filename=saved_name,
            original_filename=file.filename,
            file_path=str(dest),
            file_type=ext,
            file_size=len(content),
            department=None,
            source="personal",
            owner_user_id=current_user.id,
            extracted_text=text,
            status=DocumentStatus.extracted,
            version=version,
        )
        db.add(doc)
        db.commit()
        db.refresh(doc)
        
        # Trigger background chunking and embedding
        background_tasks.add_task(_run_chunking_and_embedding, doc.id)
    except Exception as db_err:
        if dest.exists():
            try:
                os.remove(dest)
            except Exception:
                pass
        raise HTTPException(500, f"Failed to save document record: {db_err}")
        
    trimmed = text.strip()[:8000]
    return JSONResponse({"text": trimmed, "filename": file.filename, "chars": len(trimmed)})

