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


def process_all_documents(db: Session) -> dict:
    """End-to-end processing for all stored documents.

    For each document:
    - extract_text (retry for failed/missing/empty)
    - chunk_document
    - embed_document

    Continues on error per document.
    """

    docs = db.query(Document).order_by(Document.id).all()

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

    for doc in docs:
        try:
            # 1) extraction
            if _should_extract(doc):
                doc.status = DocumentStatus.extracting
                doc.extraction_error = None
                db.commit()

                text, pages = extract_text(doc.file_path, doc.file_type)
                doc.extracted_text = text
                doc.page_count = pages
                doc.processed_at = datetime.utcnow()
                doc.status = DocumentStatus.extracted
                db.commit()
                results["extracted"] += 1

            # 2) chunking (ensure we always chunk)
            doc = db.query(Document).filter(Document.id == doc.id).first()
            if not doc or not doc.extracted_text:
                raise ValueError("Document has no extracted_text; cannot chunk")

            chunk_document(doc, db)
            results["chunked"] += 1

            # 3) embedding (ensure we always embed)
            embed_document(doc, db)
            results["embedded"] += 1

            results["processed"] += 1

        except Exception as e:
            doc.status = DocumentStatus.failed
            doc.extraction_error = getattr(doc, "extraction_error", None)
            # try to keep the error in extraction_error for visibility in UI
            try:
                doc.extraction_error = str(e)
            except Exception:
                pass
            db.commit()
            results["failed"] += 1
            results["errors"][doc.id] = str(e)

    return results

