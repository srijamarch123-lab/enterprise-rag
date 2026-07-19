"""
Personal Google Drive connector - same mechanics as /api/drive, but scoped
to the authenticated user's own private documents. owner_user_id always
comes from the session (never trusted from the client).
"""
import uuid
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Document, User
from app.config.settings import get_settings
from app.services.auth import get_current_user
from app.routes.upload import _run_extraction
from app.routes.drive import _get_service, _download_and_save, SUPPORTED_MIME_TYPES

settings = get_settings()
router = APIRouter(prefix="/api/personal/drive", tags=["personal-drive"])


class DriveRequest(BaseModel):
    credentials_json: dict
    folder_id: str | None = None


class ImportRequest(BaseModel):
    credentials_json: dict
    file: dict


class ImportAllRequest(BaseModel):
    credentials_json: dict
    files: list[dict]


@router.post("/files")
def list_personal_files(req: DriveRequest, current_user: User = Depends(get_current_user)):
    try:
        service = _get_service(req.credentials_json)
        query = " or ".join(f"mimeType='{m}'" for m in SUPPORTED_MIME_TYPES)
        if req.folder_id:
            query = f"({query}) and '{req.folder_id}' in parents and trashed=false"
        results = service.files().list(
            q=query,
            fields="files(id, name, mimeType, size, modifiedTime)",
            pageSize=100,
        ).execute()
        files = []
        for f in results.get("files", []):
            files.append({
                "drive_file_id": f["id"],
                "name": f["name"],
                "file_type": SUPPORTED_MIME_TYPES.get(f["mimeType"], "unknown"),
                "size": int(f.get("size", 0)),
            })
        return files
    except Exception as e:
        raise HTTPException(500, str(e))


@router.post("/import")
def import_personal_file(
    req: ImportRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    existing = db.query(Document).filter(
        Document.original_filename == req.file["name"],
        Document.owner_user_id == current_user.id,
    ).first()
    if existing:
        return {"id": existing.id, "filename": req.file["name"], "skipped": True}

    try:
        saved_name, dest, size = _download_and_save(req.credentials_json, req.file)
    except Exception as e:
        raise HTTPException(500, f"Download failed: {e}")

    doc = Document(
        filename=saved_name,
        original_filename=req.file["name"],
        file_path=dest,
        file_type=req.file["file_type"],
        file_size=size,
        source="personal_drive",
        drive_file_id=req.file["drive_file_id"],
        owner_user_id=current_user.id,
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)

    background_tasks.add_task(_run_extraction, doc.id)

    return {"id": doc.id, "filename": req.file["name"], "skipped": False}


@router.post("/import-all")
def import_all_personal(
    req: ImportAllRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from concurrent.futures import ThreadPoolExecutor

    def process_personal_import(f):
        existing = db.query(Document).filter(
            Document.original_filename == f["name"],
            Document.owner_user_id == current_user.id,
        ).first()
        if existing:
            return {"id": existing.id, "filename": f["name"], "skipped": True}
        try:
            saved_name, dest, size = _download_and_save(req.credentials_json, f)
            doc = Document(
                filename=saved_name,
                original_filename=f["name"],
                file_path=dest,
                file_type=f["file_type"],
                file_size=size,
                source="personal_drive",
                drive_file_id=f["drive_file_id"],
                owner_user_id=current_user.id,
            )
            db.add(doc)
            db.commit()
            db.refresh(doc)
            background_tasks.add_task(_run_extraction, doc.id)
            return {"id": doc.id, "filename": f["name"], "skipped": False}
        except Exception as e:
            return {"filename": f["name"], "error": str(e)}

    with ThreadPoolExecutor(max_workers=min(10, len(req.files) or 1)) as executor:
        results = list(executor.map(process_personal_import, req.files))

    return results
