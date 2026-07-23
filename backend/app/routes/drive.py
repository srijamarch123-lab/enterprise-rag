"""
Drive connector — accepts service account JSON key directly from the UI.
Returns document ID immediately so frontend can track pipeline progress.
"""
import uuid
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Document
from app.config.settings import get_settings
from app.services.process_all import process_all_documents

settings = get_settings()
router = APIRouter(prefix="/api/drive", tags=["drive"])
UPLOAD_DIR = Path(settings.upload_dir)
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

SUPPORTED_MIME_TYPES = {
    "application/pdf": "pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx",
    "application/msword": "doc",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation": "pptx",
    "application/vnd.ms-powerpoint": "ppt",
    "text/plain": "txt",
    "image/png": "png",
    "image/jpeg": "jpeg",
    "image/jpg": "jpg",
    "text/csv": "csv",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": "xlsx",
    "application/vnd.ms-excel": "xls",
    "text/markdown": "md",
    "text/x-markdown": "md",
    "application/vnd.google-apps.spreadsheet": "xlsx",
    "application/vnd.google-apps.document": "docx",
    "application/vnd.google-apps.presentation": "pptx",
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
    
    # Check if this is a service account credentials json
    required_keys = ["type", "project_id", "private_key_id", "private_key", "client_email"]
    missing = [k for k in required_keys if k not in credentials_json]
    if missing:
        raise ValueError(
            f"Invalid Service Account JSON. Missing required fields: {', '.join(missing)}. "
            "Make sure you are uploading a Service Account Key JSON from the Google Cloud Console "
            "(IAM & Admin -> Service Accounts -> Keys), and not an OAuth client ID credential."
        )

    SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]
    creds = service_account.Credentials.from_service_account_info(credentials_json, scopes=SCOPES)
    return build("drive", "v3", credentials=creds)


def _download_and_save(credentials_json: dict, drive_meta: dict) -> tuple[str, str, int]:
    from googleapiclient.http import MediaIoBaseDownload
    import io
    service = _get_service(credentials_json)
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    saved_name = f"{uuid.uuid4().hex}.{drive_meta['file_type']}"
    dest = str(UPLOAD_DIR / saved_name)
    
    file_id = drive_meta["drive_file_id"]
    meta = service.files().get(fileId=file_id, fields="mimeType").execute()
    mime_type = meta.get("mimeType")
    
    if mime_type == "application/vnd.google-apps.spreadsheet":
        request = service.files().export_media(
            fileId=file_id,
            mimeType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    elif mime_type == "application/vnd.google-apps.document":
        request = service.files().export_media(
            fileId=file_id,
            mimeType="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        )
    elif mime_type == "application/vnd.google-apps.presentation":
        request = service.files().export_media(
            fileId=file_id,
            mimeType="application/vnd.openxmlformats-officedocument.presentationml.presentation"
        )
    else:
        request = service.files().get_media(fileId=file_id)
        
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
        # Save credentials to settings.google_credentials_path so background sync/redownloads can use it
        import json
        with open(settings.google_credentials_path, "w", encoding="utf-8") as f:
            json.dump(req.credentials_json, f, indent=2)

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


def _run_process_all():
    from app.database import SessionLocal
    db = SessionLocal()
    try:
        process_all_documents(db)
    finally:
        db.close()


@router.post("/import")
def import_file(req: ImportRequest, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
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
        # Save credentials to settings.google_credentials_path
        import json
        with open(settings.google_credentials_path, "w", encoding="utf-8") as f:
            json.dump(req.credentials_json, f, indent=2)

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
    background_tasks.add_task(_run_process_all)
    return {"id": doc.id, "filename": req.file["name"], "skipped": False}


@router.post("/import-all")
def import_all(req: ImportAllRequest, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    if req.files:
        try:
            import json
            with open(settings.google_credentials_path, "w", encoding="utf-8") as f:
                json.dump(req.credentials_json, f, indent=2)
        except Exception as e:
            raise HTTPException(500, f"Failed to save credentials: {e}")

    from concurrent.futures import ThreadPoolExecutor
    from app.database import SessionLocal

    def process_file_import(f):
        thread_db = SessionLocal()
        try:
            existing = thread_db.query(Document).filter(
                Document.original_filename == f["name"]
            ).first()
            if existing:
                return {"id": existing.id, "filename": f["name"], "skipped": True}
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
            thread_db.add(doc)
            thread_db.commit()
            thread_db.refresh(doc)
            return {"id": doc.id, "filename": f["name"], "skipped": False}
        except Exception as e:
            thread_db.rollback()
            try:
                failed_doc = Document(
                    filename=f["name"],
                    original_filename=f["name"],
                    file_path="",
                    file_type=f.get("file_type", "unknown"),
                    file_size=0,
                    source="drive",
                    drive_file_id=f.get("drive_file_id"),
                    status="failed",
                    extraction_error=str(e),
                )
                thread_db.add(failed_doc)
                thread_db.commit()
            except Exception:
                thread_db.rollback()
            return {"filename": f["name"], "error": str(e)}
        finally:
            thread_db.close()

    with ThreadPoolExecutor(max_workers=min(10, len(req.files) or 1)) as executor:
        results = list(executor.map(process_file_import, req.files))

    # Auto-process all newly imported documents via background task
    background_tasks.add_task(_run_process_all)
    return results