"""
POST /documents/{id}/chunk         — chunk a single document
POST /chunk/all                    — chunk all extracted docs
GET  /documents/{id}/chunks        — list chunks for a document
GET  /chunks/{chunk_id}            — get single chunk
"""
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Chunk, Document, DocumentStatus
from app.services.chunker import chunk_document, chunk_all_documents

router = APIRouter(prefix="/api", tags=["chunks"])


@router.post("/documents/{doc_id}/chunk")
def chunk_single(doc_id: int, db: Session = Depends(get_db)):
    doc = db.query(Document).filter(Document.id == doc_id).first()
    if not doc:
        raise HTTPException(404, "Document not found")
    if not doc.extracted_text:
        raise HTTPException(400, "Document has no extracted text yet")
    chunks = chunk_document(doc, db)
    return {"document_id": doc_id, "chunks_created": len(chunks)}


@router.post("/chunk/all")
def chunk_all(db: Session = Depends(get_db)):
    return chunk_all_documents(db)


@router.get("/documents/{doc_id}/chunks")
def list_chunks(doc_id: int, db: Session = Depends(get_db)):
    doc = db.query(Document).filter(Document.id == doc_id).first()
    if not doc:
        raise HTTPException(404, "Document not found")
    chunks = (
        db.query(Chunk)
        .filter(Chunk.document_id == doc_id)
        .order_by(Chunk.chunk_index)
        .all()
    )
    return [
        {
            "id": c.id,
            "chunk_index": c.chunk_index,
            "token_count": c.token_count,
            "page_number": c.page_number,
            "is_embedded": c.is_embedded,
            "text_preview": c.text[:200],
        }
        for c in chunks
    ]


@router.get("/chunks/{chunk_id}")
def get_chunk(chunk_id: int, db: Session = Depends(get_db)):
    chunk = db.query(Chunk).filter(Chunk.id == chunk_id).first()
    if not chunk:
        raise HTTPException(404, "Chunk not found")
    return {
        "id": chunk.id,
        "document_id": chunk.document_id,
        "chunk_index": chunk.chunk_index,
        "token_count": chunk.token_count,
        "page_number": chunk.page_number,
        "is_embedded": chunk.is_embedded,
        "qdrant_point_id": chunk.qdrant_point_id,
        "text": chunk.text,
    }
