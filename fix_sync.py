content = open('backend/app/routes/drive_connections.py', 'r', encoding='utf-8').read()

old = '''@router.post("/{connection_id}/sync")
def sync_connection(connection_id: int, background_tasks: BackgroundTasks, db: Session = Depends(get_db), current_user=Depends(require_admin)):
    conn = db.query(DriveConnection).filter(DriveConnection.id == connection_id).first()
    if not conn:
        raise HTTPException(status_code=404, detail="Connection not found")
    background_tasks.add_task(process_all_documents, db)
    conn.last_synced = datetime.utcnow()
    db.commit()
    return {"message": "Sync started"}'''

new = '''@router.post("/{connection_id}/sync")
def sync_connection(connection_id: int, background_tasks: BackgroundTasks, db: Session = Depends(get_db), current_user=Depends(require_admin)):
    conn = db.query(DriveConnection).filter(DriveConnection.id == connection_id).first()
    if not conn:
        raise HTTPException(status_code=404, detail="Connection not found")
    
    try:
        from googleapiclient.discovery import build
        from google.oauth2.service_account import Credentials
        from app.models import Document, DocumentStatus
        from pathlib import Path
        import uuid, requests as req_lib

        creds = Credentials.from_service_account_info(
            conn.credentials_json,
            scopes=["https://www.googleapis.com/auth/drive.readonly"]
        )
        service = build("drive", "v3", credentials=creds)
        query = "mimeType != 'application/vnd.google-apps.folder' and trashed = false"
        if conn.folder_id:
            query += f" and '{conn.folder_id}' in parents"
        
        results = service.files().list(q=query, fields="files(id,name,mimeType,size)").execute()
        files = results.get("files", [])
        
        # Find existing drive file IDs
        existing_ids = {d.drive_file_id for d in db.query(Document).filter(Document.source == "drive").all() if d.drive_file_id}
        
        new_docs = []
        for f in files:
            if f["id"] in existing_ids:
                continue
            # Download and save file
            try:
                from app.routes.drive import SUPPORTED_MIME_TYPES, UPLOAD_DIR
                ext = SUPPORTED_MIME_TYPES.get(f.get("mimeType", ""), None)
                if not ext:
                    continue
                file_data = service.files().get_media(fileId=f["id"]).execute()
                file_path = UPLOAD_DIR / f"{uuid.uuid4().hex}.{ext}"
                file_path.write_bytes(file_data)
                doc = Document(
                    original_filename=f["name"],
                    file_path=str(file_path),
                    file_type=ext,
                    source="drive",
                    drive_file_id=f["id"],
                    status=DocumentStatus.pending,
                )
                db.add(doc)
                new_docs.append(f["name"])
            except Exception as e:
                print(f"Failed to import {f['name']}: {e}")
        
        db.commit()
        conn.last_synced = datetime.utcnow()
        db.commit()
        
        if new_docs:
            background_tasks.add_task(process_all_documents, db)
        
        return {
            "message": f"Sync complete. Found {len(new_docs)} new document(s).",
            "new_documents": new_docs,
            "total_in_drive": len(files),
            "new_count": len(new_docs)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Sync failed: {str(e)}")'''

if old in content:
    content = content.replace(old, new)
    open('backend/app/routes/drive_connections.py', 'w', encoding='utf-8').write(content)
    print('Done')
else:
    print('FAILED')
