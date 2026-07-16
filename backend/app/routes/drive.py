"""
Drive connector — accepts service account JSON key directly from the UI.
Returns document ID immediately so frontend can track pipeline progress.
"""
import uuid
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Document
from app.config.settings import get_settings

settings = get_settings()
router = APIRouter(prefix="/api/drive", tags=["drive"])
UPLOAD_DIR = Path(settings.upload_dir)
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

SUPPORTED_MIME_TYPES = {
    "application/pdf": "pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation": "pptx",
    "text/plain": "txt",
}


class DriveRequest(BaseModel):
    credentials_json: dict
    folder_id: str | None = None


class ImportRequest(BaseModel):
    credentials_json: dict
    file: dict


class ImportAllRequest(BaseModel):
    credentials_json: dict
    files: list[dict]


def _get_service(credentials_json: dict):
    from google.oauth2 import service_account
    from googleapiclient.discovery import build
    SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]
    creds = service_account.Credentials.from_service_account_info(credentials_json, scopes=SCOPES)
    return build("drive", "v3", credentials=creds)


def _download_and_save(credentials_json: dict, drive_meta: dict) -> tuple[str, str, int]:
    from googleapiclient.http import MediaIoBaseDownload
    import io
    service = _get_service(credentials_json)
    saved_name = f"{uuid.uuid4().hex}.{drive_meta['file_type']}"
    dest = str(UPLOAD_DIR / saved_name)
    request = service.files().get_media(fileId=drive_meta["drive_file_id"])
    buf = io.BytesIO()
    downloader = MediaIoBaseDownload(buf, request)
    done = False
    while not done:
        _, done = downloader.next_chunk()
    Path(dest).write_bytes(buf.getvalue())
    return saved_name, dest, len(buf.getvalue())


@router.post("/files")
def list_files(req: DriveRequest):
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
def import_file(req: ImportRequest, db: Session = Depends(get_db)):
    """
    Downloads file from Drive, saves to disk, creates DB record.
    Returns document ID immediately — frontend handles pipeline.
    Skips if file with same name already exists.
    """
    # Duplicate check
    existing = db.query(Document).filter(
        Document.original_filename == req.file["name"]
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
        source="drive",
        drive_file_id=req.file["drive_file_id"],
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)
    return {"id": doc.id, "filename": req.file["name"], "skipped": False}


@router.post("/import-all")
def import_all(req: ImportAllRequest, db: Session = Depends(get_db)):
    results = []
    for f in req.files:
        existing = db.query(Document).filter(
            Document.original_filename == f["name"]
        ).first()
        if existing:
            results.append({"id": existing.id, "filename": f["name"], "skipped": True})
            continue
        try:
            saved_name, dest, size = _download_and_save(req.credentials_json, f)
            doc = Document(
                filename=saved_name,
                original_filename=f["name"],
                file_path=dest,
                file_type=f["file_type"],
                file_size=size,
                source="drive",
                drive_file_id=f["drive_file_id"],
            )
            db.add(doc)
            db.commit()
            db.refresh(doc)
            results.append({"id": doc.id, "filename": f["name"], "skipped": False})
        except Exception as e:
            results.append({"filename": f["name"], "error": str(e)})
    # Auto-process all newly imported documents
    try:
        from app.services.process_all import process_all_documents
        import threading
        t = threading.Thread(target=process_all_documents, args=(db,))
        t.daemon = True
        t.start()
    except Exception as e:
        pass
    return results