from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from qdrant_client.models import FieldCondition, MatchValue

from app.database import SessionLocal, get_db
from app.models import Chunk, User, Document
from app.services.auth import get_current_user
from app.services.embedder import _get_qdrant
from app.services.query_embedder import embed_query
from app.services.query_processor import normalize_query
from app.services.llm_service import build_answer
from app.services.rbac_filter import build_rbac_filter
from app.config.settings import get_settings

from app.routes.search_v1 import (
    _get_visible_doc_ids_for_role,
    _bm25_search,
    _merge_results,
    RERANK_TOP_K,
    CONFIDENCE_THRESHOLD,
)

import logging

logger = logging.getLogger(__name__)
settings = get_settings()
router = APIRouter(prefix="/api", tags=["chat"])


class ChatRequest(BaseModel):
    query: str
    limit: int = 10
    department: Optional[str] = None
    keyword_backend: Optional[str] = None
    stream: bool = False


def _make_chat_filter(role: str, user_id: int, department: Optional[str]):
    """Same as the org RBAC filter, but OR'd with an exact owner_id match
    so a user's own personal uploads are also searchable in their chat -
    without making them visible to anyone else, including admins."""
    base = build_rbac_filter(role)
    base.should.append(
        FieldCondition(key="owner_id", match=MatchValue(value=user_id))
    )
    if department:
        base.must = base.must or []
        base.must.append(FieldCondition(key="department", match=MatchValue(value=department)))
    return base


@router.post("/chat")
def chat(
    req: ChatRequest,
    current_user: User = Depends(get_current_user),
    db: SessionLocal = Depends(get_db),
):
    try:
        if not req.query or not req.query.strip():
            raise HTTPException(status_code=400, detail="Query cannot be empty")

        normalized = normalize_query(req.query)
        if not normalized:
            raise HTTPException(status_code=400, detail="Query is empty after normalization")

        # Org-visible docs (role-based) + this user's own personal docs
        visible_doc_ids = _get_visible_doc_ids_for_role(str(current_user.role), db)
        personal_doc_ids = {
            d.id for d in db.query(Document).filter(Document.owner_user_id == current_user.id).all()
        }
        visible_doc_ids = visible_doc_ids | personal_doc_ids

        query_vector = embed_query(normalized)
        if not query_vector:
            raise HTTPException(status_code=400, detail="Empty query vector")

        query_filter = _make_chat_filter(str(current_user.role), current_user.id, req.department)
        client = _get_qdrant()
        top_k = req.limit

        semantic_hits = client.query_points(
            collection_name=settings.qdrant_collection_name,
            query=query_vector,
            query_filter=query_filter,
            limit=top_k,
            with_payload=True,
        ).points

        keyword_backend = (req.keyword_backend or "bm25").strip().lower()
        bm25_results = _bm25_search(normalized, visible_doc_ids, db, top_k=top_k * 2)

        for b in bm25_results:
            if b.get("document_id"):
                doc = db.query(Document).filter(Document.id == b["document_id"]).first()
                if doc:
                    b["department"] = doc.department
                    b["access_level"] = doc.access_level
                    b["filename"] = doc.original_filename

        merged_results, has_answer = _merge_results(
            semantic_hits,
            bm25_results,
            top_k=RERANK_TOP_K,
            confidence_threshold=CONFIDENCE_THRESHOLD,
        )

        for r in merged_results:
            if r.get("document_id"):
                doc = db.query(Document).filter(Document.id == r["document_id"]).first()
                if doc:
                    r["file_path"] = doc.file_path
            if r.get("chunk_id"):
                chunk_row = db.query(Chunk).filter(Chunk.id == r["chunk_id"]).first()
                if chunk_row:
                    r["full_text"] = chunk_row.text

        if req.stream:
            from fastapi.responses import StreamingResponse
            import json

            def event_generator():
                serializable_results = []
                for r in merged_results:
                    serializable_results.append({
                        "chunk_id": r.get("chunk_id"),
                        "document_id": r.get("document_id"),
                        "chunk_index": r.get("chunk_index"),
                        "page_number": r.get("page_number"),
                        "text_preview": r.get("text_preview"),
                        "department": r.get("department"),
                        "access_level": r.get("access_level"),
                        "filename": r.get("filename"),
                        "file_path": r.get("file_path"),
                        "combined_score": r.get("combined_score"),
                    })

                yield f"data: {json.dumps({'event': 'metadata', 'results': serializable_results, 'has_answer': has_answer})}\n\n"

                if has_answer and merged_results:
                    try:
                        from app.services.llm_service import build_answer_stream
                        context_chunks = [
                            {
                                "text": r.get("full_text") or r.get("text_preview", ""),
                                "filename": r.get("filename"),
                                "document_id": r.get("document_id"),
                                "page_number": r.get("page_number"),
                                "chunk_index": r.get("chunk_index"),
                            }
                            for r in merged_results
                        ]
                        for token in build_answer_stream(req.query, context_chunks):
                            yield f"data: {json.dumps({'event': 'token', 'token': token})}\n\n"
                    except Exception as e:
                        logger.error(f"Streaming LLM failed: {e}")
                        yield f"data: {json.dumps({'event': 'error', 'error': str(e)})}\n\n"

                yield "data: [DONE]\n\n"

            return StreamingResponse(event_generator(), media_type="text/event-stream")

        answer = ""
        if has_answer and merged_results:
            try:
                context_chunks = [
                    {
                        "text": r.get("full_text") or r.get("text_preview", ""),
                        "filename": r.get("filename"),
                        "document_id": r.get("document_id"),
                        "page_number": r.get("page_number"),
                        "chunk_index": r.get("chunk_index"),
                    }
                    for r in merged_results
                ]
                answer = build_answer(req.query, context_chunks)
            except Exception as e:
                logger.error(f"LLM answer generation failed: {e}")
                answer = ""

        return {
            "query": req.query,
            "normalized_query": normalized,
            "role": current_user.role,
            "answer": answer,
            "results": merged_results,
            "has_answer": has_answer,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
