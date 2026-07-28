from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel
from sqlalchemy.orm import Session
from datetime import datetime
from app.database import get_db
from app.models import DriveConnection
from app.dependencies.rbac import require_admin

router = APIRouter(prefix="/api/drive-connections", tags=["drive-connections"])

class DriveConnectionCreate(BaseModel):
    name: str = "Google Drive"
    credentials_json: dict
    folder_id: str | None = None

@router.get("")
def list_connections(db: Session = Depends(get_db), current_user=Depends(require_admin)):
    connections = db.query(DriveConnection).order_by(DriveConnection.id).all()
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
    from app.routes.drive import ImportAllRequest, import_all
    conn = db.query(DriveConnection).filter(DriveConnection.id == connection_id).first()
    if not conn:
        raise HTTPException(status_code=404, detail="Connection not found")

    try:
        from googleapiclient.discovery import build
        from google.oauth2.service_account import Credentials
        creds = Credentials.from_service_account_info(conn.credentials_json, scopes=["https://www.googleapis.com/auth/drive.readonly"])
        service = build("drive", "v3", credentials=creds)
        query = "mimeType != 'application/vnd.google-apps.folder' and trashed = false"
        if conn.folder_id:
            query += f" and '{conn.folder_id}' in parents"
        results = service.files().list(q=query, fields="files(id,name,mimeType)").execute()
        files = results.get("files", [])

        from app.models import Document
        existing_ids = {d.drive_file_id for d in db.query(Document).filter(Document.source == 'drive').all() if d.drive_file_id}
        existing_names = {d.original_filename for d in db.query(Document).filter(Document.status == 'embedded').all()}
        new_files = [f for f in files if f['id'] not in existing_ids and f['name'] not in existing_names]

        if new_files:
            req = ImportAllRequest(credentials_json=conn.credentials_json, files=new_files)
            import_all(req, background_tasks=background_tasks, db=db)

        conn.last_synced = datetime.utcnow()
        db.commit()

        return {
            "message": f"Sync complete. {len(new_files)} new document(s) found." if new_files else "No new documents found. Everything is up to date.",
            "new_count": len(new_files),
            "new_documents": [f["name"] for f in new_files],
            "total_in_drive": len(files)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Sync failed: {str(e)}")
