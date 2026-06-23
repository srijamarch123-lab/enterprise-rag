"""
POST /documents/{id}/embed         — embed a single document
POST /embed/all                    — embed all chunked docs
GET  /documents/{id}/embedding-status
GET  /qdrant/stats
POST /documents/{id}/reprocess
"""
from fastapi import APIRouter, Depends, HTTPException
from app.dependencies.rbac import require_manager_or_above, require_admin
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Chunk, Document
from app.services.embedder import (
    embed_document,
    embed_all_documents,
    reprocess_document,
    get_qdrant_stats,
    check_already_embedded,
)

router = APIRouter(prefix="/api", tags=["embeddings"])


@router.post("/documents/{doc_id}/embed", dependencies=[Depends(require_manager_or_above)])
def embed_single(doc_id: int, db: Session = Depends(get_db)):
    doc = db.query(Document).filter(Document.id == doc_id).first()
    if not doc:
        raise HTTPException(404, "Document not found")
    result = embed_document(doc, db)
    return {"document_id": doc_id, **result}


@router.post("/embed/all", dependencies=[Depends(require_manager_or_above)])
def embed_all(db: Session = Depends(get_db)):
    return embed_all_documents(db)


@router.get("/documents/{doc_id}/embedding-status")
def embedding_status(doc_id: int, db: Session = Depends(get_db)):
    doc = db.query(Document).filter(Document.id == doc_id).first()
    if not doc:
        raise HTTPException(404, "Document not found")
    chunks = db.query(Chunk).filter(Chunk.document_id == doc_id).all()
    embedded = sum(1 for c in chunks if c.is_embedded)
    return {
        "document_id": doc_id,
        "status": doc.status,
        "total_chunks": len(chunks),
        "embedded_chunks": embedded,
        "pending_chunks": len(chunks) - embedded,
        "fully_embedded": check_already_embedded(doc_id, db),
    }


@router.get("/qdrant/stats", dependencies=[Depends(require_admin)])
def qdrant_stats():
    return get_qdrant_stats()


@router.post("/documents/{doc_id}/reprocess", dependencies=[Depends(require_manager_or_above)])
def reprocess(doc_id: int, db: Session = Depends(get_db)):
    try:
        result = reprocess_document(doc_id, db)
        return {"document_id": doc_id, **result}
    except ValueError as e:
        raise HTTPException(404, str(e))
    except Exception as e:
        raise HTTPException(500, str(e))
