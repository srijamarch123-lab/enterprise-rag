from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel
from sqlalchemy.orm import Session
from datetime import datetime
from app.database import get_db
from app.models import DriveConnection
from app.dependencies.rbac import require_admin
from app.services.process_all import process_all_documents

router = APIRouter(prefix="/api/drive-connections", tags=["drive-connections"])

class DriveConnectionCreate(BaseModel):
    name: str = "Google Drive"
    credentials_json: dict
    folder_id: str | None = None

@router.get("")
def list_connections(db: Session = Depends(get_db), current_user=Depends(require_admin)):
    connections = db.query(DriveConnection).all()
    return [{"id": c.id, "name": c.name, "folder_id": c.folder_id, "created_at": c.created_at, "last_synced": c.last_synced, "email": c.credentials_json.get("client_email", "Unknown") if c.credentials_json else "Unknown"} for c in connections]

@router.post("")
def create_connection(body: DriveConnectionCreate, db: Session = Depends(get_db), current_user=Depends(require_admin)):
    conn = DriveConnection(name=body.name, credentials_json=body.credentials_json, folder_id=body.folder_id, created_by=current_user.id)
    db.add(conn)
    db.commit()
    db.refresh(conn)
    return {"id": conn.id, "name": conn.name, "message": "Drive connected successfully"}

@router.delete("/{connection_id}")
def delete_connection(connection_id: int, db: Session = Depends(get_db), current_user=Depends(require_admin)):
    conn = db.query(DriveConnection).filter(DriveConnection.id == connection_id).first()
    if not conn:
        raise HTTPException(status_code=404, detail="Connection not found")
    db.delete(conn)
    db.commit()
    return {"message": "Connection removed"}

@router.post("/{connection_id}/sync")
def sync_connection(connection_id: int, background_tasks: BackgroundTasks, db: Session = Depends(get_db), current_user=Depends(require_admin)):
    conn = db.query(DriveConnection).filter(DriveConnection.id == connection_id).first()
    if not conn:
        raise HTTPException(status_code=404, detail="Connection not found")

    credentials_json = conn.credentials_json
    folder_id = conn.folder_id

    def _do_sync():
        from googleapiclient.discovery import build
        from google.oauth2.service_account import Credentials
        from app.models import Document, DocumentStatus
        from app.database import SessionLocal as _SL
        from app.routes.drive import SUPPORTED_MIME_TYPES, UPLOAD_DIR
        import uuid
        _db = _SL()
        try:
            creds = Credentials.from_service_account_info(credentials_json, scopes=["https://www.googleapis.com/auth/drive.readonly"])
            service = build("drive", "v3", credentials=creds)
            query = "mimeType != 'application/vnd.google-apps.folder' and trashed = false"
            if folder_id:
                query += f" and '{folder_id}' in parents"
            results = service.files().list(q=query, fields="files(id,name,mimeType)").execute()
            files = results.get("files", [])
            existing_ids = {d.drive_file_id for d in _db.query(Document).filter(Document.source == "drive").all() if d.drive_file_id}
            new_docs = []
            for f in files:
                if f["id"] in existing_ids:
                    continue
                try:
                    ext = SUPPORTED_MIME_TYPES.get(f.get("mimeType", ""), None)
                    if not ext:
                        continue
                    file_data = service.files().get_media(fileId=f["id"]).execute()
                    file_path = UPLOAD_DIR / f"{uuid.uuid4().hex}.{ext}"
                    file_path.write_bytes(file_data)
                    doc = Document(original_filename=f["name"], file_path=str(file_path), file_type=ext, source="drive", drive_file_id=f["id"], status=DocumentStatus.pending)
                    _db.add(doc)
                    new_docs.append(f["name"])
                except Exception as e:
                    print(f"Failed to import {f['name']}: {e}")
            _db.commit()
            _conn = _db.query(DriveConnection).filter(DriveConnection.id == connection_id).first()
            if _conn:
                _conn.last_synced = datetime.utcnow()
                _db.commit()
            if new_docs:
                process_all_documents(_db)
            print(f"Sync complete: {len(new_docs)} new docs")
        except Exception as e:
            print(f"Sync error: {e}")
        finally:
            _db.close()

    background_tasks.add_task(_do_sync)
    return {"message": "Sync started in background. Check Documents page for progress.", "queued": True}
