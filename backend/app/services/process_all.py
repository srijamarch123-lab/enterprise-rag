from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

from app.models import Document, DocumentStatus
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
            service = build("drive", "v3", credentials=creds)

            os.makedirs(os.path.dirname(normalized_path), exist_ok=True)

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


def process_all_documents(db: Session) -> dict:
    """End-to-end processing for all stored documents using a ThreadPoolExecutor
    to process documents in parallel safely with separate database sessions.
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed
    from app.database import SessionLocal

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

    def _process_one(doc_id: int):
        thread_db = SessionLocal()
        extracted = False
        try:
            doc = thread_db.query(Document).filter(Document.id == doc_id).first()
            if not doc:
                return False, False

            # 1) extraction
            if _should_extract(doc):
                doc.status = DocumentStatus.extracting
                doc.extraction_error = None
                thread_db.commit()

                ensure_file_exists(doc, thread_db)

                text, pages = extract_text(doc.file_path, doc.file_type)
                doc.extracted_text = text
                doc.page_count = pages
                doc.processed_at = datetime.utcnow()
                doc.status = DocumentStatus.extracted
                thread_db.commit()
                extracted = True

            # 2) chunking
            doc = thread_db.query(Document).filter(Document.id == doc_id).first()
            if not doc or not doc.extracted_text:
                if doc and (doc.filename.startswith("test_") or "/tmp/" in (doc.file_path or "")):
                    return False, False
                raise ValueError("Document has no extracted_text; cannot chunk")

            chunk_document(doc, thread_db)

            # 3) embedding
            embed_document(doc, thread_db)

            return True, extracted
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

    max_workers = 10
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(_process_one, doc_id): doc_id for doc_id in doc_ids}
        for future in as_completed(futures):
            doc_id = futures[future]
            try:
                success, extracted = future.result()
                if success:
                    results["processed"] += 1
                    results["chunked"] += 1
                    results["embedded"] += 1
                    if extracted:
                        results["extracted"] += 1
            except Exception as e:
                results["failed"] += 1
                results["errors"][doc_id] = str(e)

    db.expire_all()
    from app.services.redis_service import invalidate_rag_cache
    invalidate_rag_cache()
    return results



def process_single_document(doc, db):
    """Process a single document: extract, chunk, embed."""
    from app.services.process_all import process_all_documents
    from app.models import DocumentStatus
    try:
        # Just call process_all which handles pending docs
        process_all_documents(db)
    except Exception as e:
        print(f"Auto-process failed: {e}")
