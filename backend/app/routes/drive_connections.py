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
    background_tasks.add_task(process_all_documents, db)
    conn.last_synced = datetime.utcnow()
    db.commit()
    return {"message": "Sync started"}
