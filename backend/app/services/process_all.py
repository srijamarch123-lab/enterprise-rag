from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.models import Document, DocumentStatus, Chunk
from app.services.chunker import chunk_document
from app.services.embedder import embed_document
from app.services.extractor import extract_text


def _should_extract(doc: Document) -> bool:
    if doc.file_path and ("/tmp/" in doc.file_path or "\\tmp\\" in doc.file_path):
        return False
    if doc.filename and doc.filename.startswith("test_"):
        return False
    return (
        doc.status in {DocumentStatus.failed, DocumentStatus.pending, DocumentStatus.extracting}
        or not doc.extracted_text
    )


def ensure_file_exists(doc: Document, db: Session):
    import os
    from pathlib import Path
    
    # Standardize path for operating system
    normalized_path = os.path.normpath(doc.file_path)
    
    if not os.path.isabs(normalized_path):
        backend_dir = Path(__file__).parent.parent.parent.resolve()
        normalized_path = str((backend_dir / normalized_path).resolve())
        doc.file_path = normalized_path
        db.commit()

    if os.path.exists(normalized_path):
        return

    if doc.source == "drive" and doc.drive_file_id:
        try:
            from app.config.settings import get_settings
            from google.oauth2 import service_account
            from googleapiclient.discovery import build
            from googleapiclient.http import MediaIoBaseDownload
            import io
            import json

            settings = get_settings()
            creds_path = settings.google_credentials_path
            
            if not os.path.exists(creds_path):
                if not os.path.isabs(creds_path):
                    fallback = Path(__file__).parent.parent.parent / creds_path
                    if fallback.exists():
                        creds_path = str(fallback.resolve())
                    else:
                        raise FileNotFoundError(f"Google credentials file not found at {creds_path}")
                else:
                    raise FileNotFoundError(f"Google credentials file not found at {creds_path}")

            with open(creds_path, "r", encoding="utf-8") as f:
                creds_json = json.load(f)

            SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]
            creds = service_account.Credentials.from_service_account_info(creds_json, scopes=SCOPES)
            service: Any = build("drive", "v3", credentials=creds)

            os.makedirs(os.path.dirname(normalized_path), exist_ok=True)

            meta = service.files().get(fileId=doc.drive_file_id, fields="mimeType").execute()
            mime_type = meta.get("mimeType")

            if mime_type == "application/vnd.google-apps.spreadsheet":
                request = service.files().export_media(
                    fileId=doc.drive_file_id,
                    mimeType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
            elif mime_type == "application/vnd.google-apps.document":
                request = service.files().export_media(
                    fileId=doc.drive_file_id,
                    mimeType="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                )
            elif mime_type == "application/vnd.google-apps.presentation":
                request = service.files().export_media(
                    fileId=doc.drive_file_id,
                    mimeType="application/vnd.openxmlformats-officedocument.presentationml.presentation"
                )
            else:
                request = service.files().get_media(fileId=doc.drive_file_id)

            buf = io.BytesIO()
            downloader = MediaIoBaseDownload(buf, request)
            done = False
            while not done:
                _, done = downloader.next_chunk()
            
            Path(normalized_path).write_bytes(buf.getvalue())
            doc.file_size = len(buf.getvalue())
            doc.file_path = normalized_path
            db.commit()

        except Exception as e:
            raise FileNotFoundError(
                f"File not found on disk, and Google Drive auto-redownload failed: {e}. "
                f"Expected file path: {normalized_path}"
            )
    else:
        raise FileNotFoundError(f"File not found on disk: {normalized_path} (Manual upload file cannot be redownloaded)")


def process_single_document_by_id(doc_id: int):
    """Process a single document safely through extract, chunk, and embed stages."""
    from app.database import SessionLocal
    thread_db = SessionLocal()
    try:
        doc = thread_db.query(Document).filter(Document.id == doc_id).first()
        if not doc:
            return False, "Document not found"

        # Self-healing for unknown/failed file types
        if not doc.file_type or doc.file_type.lower() in ("unknown", "unspecified") or doc.status == DocumentStatus.failed:
            # 1. Try to infer from original_filename or file_path or filename
            for name_source in (doc.original_filename, doc.file_path, doc.filename):
                if name_source and "." in name_source:
                    inferred = name_source.split(".")[-1].lower()
                    if inferred and inferred != "unknown":
                        doc.file_type = inferred
                        thread_db.commit()
                        break

            # 2. Try to resolve via Google Drive API if still unknown
            if (not doc.file_type or doc.file_type.lower() in ("unknown", "unspecified")) and doc.drive_file_id:
                try:
                    from googleapiclient.discovery import build
                    from google.oauth2.service_account import Credentials
                    from app.config.settings import get_settings
                    import json
                    import os
                    from pathlib import Path
                    
                    settings = get_settings()
                    creds_path = settings.google_credentials_path
                    if not os.path.isabs(creds_path):
                        fallback = Path(__file__).parent.parent.parent / creds_path
                        if fallback.exists():
                            creds_path = str(fallback.resolve())

                    if os.path.exists(creds_path):
                        with open(creds_path, "r", encoding="utf-8") as f:
                            creds_json = json.load(f)
                        creds = Credentials.from_service_account_info(creds_json, scopes=["https://www.googleapis.com/auth/drive.readonly"])
                        service: Any = build("drive", "v3", credentials=creds)
                        meta = service.files().get(fileId=doc.drive_file_id, fields="mimeType").execute()
                        mime_type = meta.get("mimeType")
                        
                        from app.routes.drive import SUPPORTED_MIME_TYPES
                        inferred = SUPPORTED_MIME_TYPES.get(mime_type)
                        if inferred:
                            doc.file_type = inferred
                            old_path = doc.file_path
                            if old_path:
                                new_path = os.path.splitext(old_path)[0] + "." + inferred
                                if os.path.exists(old_path) and old_path != new_path:
                                    try:
                                        os.rename(old_path, new_path)
                                    except Exception:
                                        pass
                                doc.file_path = new_path
                                if doc.filename:
                                    doc.filename = os.path.splitext(doc.filename)[0] + "." + inferred
                            doc.status = DocumentStatus.pending
                            thread_db.commit()
                except Exception as drive_err:
                    import logging
                    logging.getLogger(__name__).warning(f"Could not self-heal unknown Drive file {doc.id}: {drive_err}")

        # If document is in failed state, restore its status to the last successful stage
        if doc.status == DocumentStatus.failed:
            chunk_count = thread_db.query(Chunk).filter(Chunk.document_id == doc_id).count()
            if not doc.extracted_text:
                doc.status = DocumentStatus.pending
            elif chunk_count == 0:
                doc.status = DocumentStatus.extracted
            else:
                doc.status = DocumentStatus.chunked
            thread_db.commit()

        # If already embedded and has chunks, skip
        if doc.status == DocumentStatus.embedded:
            chunk_count = thread_db.query(Chunk).filter(Chunk.document_id == doc_id).count()
            if chunk_count > 0:
                return True, "already_embedded"

        # 1) extraction
        if _should_extract(doc):
            doc.status = DocumentStatus.extracting
            doc.extraction_error = None
            thread_db.commit()

            ensure_file_exists(doc, thread_db)

            text, pages = extract_text(doc.file_path, doc.file_type)
            if not text or not text.strip():
                raise ValueError("No text content could be extracted from document")

            doc.extracted_text = text
            doc.page_count = pages
            doc.processed_at = datetime.now(timezone.utc).replace(tzinfo=None)
            doc.status = DocumentStatus.extracted
            thread_db.commit()

        # 2) chunking
        doc = thread_db.query(Document).filter(Document.id == doc_id).first()
        if not doc or not doc.extracted_text:
            if doc and (doc.filename.startswith("test_") or "/tmp/" in (doc.file_path or "")):
                return False, "test_file"
            raise ValueError("Document has no extracted text; cannot chunk")

        existing_chunks = thread_db.query(Chunk).filter(Chunk.document_id == doc_id).count()
        if existing_chunks == 0 or doc.status in (DocumentStatus.extracted, DocumentStatus.pending, DocumentStatus.extracting):
            doc.status = DocumentStatus.chunking
            thread_db.commit()
            chunk_document(doc, thread_db)

        # 3) embedding
        doc = thread_db.query(Document).filter(Document.id == doc_id).first()
        if doc and doc.status != DocumentStatus.embedded:
            doc.status = DocumentStatus.embedding
            thread_db.commit()
            embed_document(doc, thread_db)

        return True, "processed"
    except Exception as e:
        try:
            doc = thread_db.query(Document).filter(Document.id == doc_id).first()
            if doc:
                doc.status = DocumentStatus.failed
                doc.extraction_error = str(e)
                thread_db.commit()
        except Exception:
            pass
        raise e
    finally:
        thread_db.close()


def process_all_documents(db: Session) -> dict:
    """End-to-end processing for all stored documents using a ThreadPoolExecutor
    to process documents in parallel safely with separate database sessions.
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed

    docs = db.query(Document).order_by(Document.id).all()
    doc_ids = [doc.id for doc in docs]

    results = {
        "total": len(docs),
        "processed": 0,
        "extracted": 0,
        "chunked": 0,
        "embedded": 0,
        "failed": 0,
        "errors": {},
        "skipped": 0,
    }

    max_workers = 4
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(process_single_document_by_id, doc_id): doc_id for doc_id in doc_ids}
        for future in as_completed(futures):
            doc_id = futures[future]
            try:
                success, reason = future.result()
                if success:
                    if reason == "already_embedded":
                        results["skipped"] += 1
                    else:
                        results["processed"] += 1
                        results["chunked"] += 1
                        results["embedded"] += 1
            except Exception as e:
                results["failed"] += 1
                results["errors"][doc_id] = str(e)

    db.expire_all()
    from app.services.redis_service import invalidate_rag_cache
    invalidate_rag_cache()
    return results


def process_single_document(doc, db):
    """Process a single document: extract, chunk, embed."""
    try:
        process_single_document_by_id(doc.id)
    except Exception as e:
        print(f"Auto-process failed for document {doc.id}: {e}")

def cleanup_stale_qdrant_points(db):
    """Remove Qdrant points whose chunk_id no longer exists in DB."""
    try:
        from app.services.embedder import _get_qdrant
        from app.config.settings import get_settings
        from app.models import Chunk
        client = _get_qdrant()
        settings = get_settings()
        pts, _ = client.scroll(collection_name=settings.qdrant_collection_name, limit=1000, with_payload=True)
        from qdrant_client.models import PointIdsList
        stale = [p.id for p in pts if p.payload and p.payload.get("chunk_id") and not db.query(Chunk).filter(Chunk.id == p.payload.get("chunk_id")).first()]
        if stale:
            client.delete(collection_name=settings.qdrant_collection_name, points_selector=PointIdsList(points=stale))
            print(f"Cleaned {len(stale)} stale Qdrant points")
    except Exception as e:
        print(f"Stale cleanup failed: {e}")
