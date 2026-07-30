from typing import Optional, Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from qdrant_client.models import FieldCondition, MatchValue
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Chunk, User, Document
from app.services.auth import get_current_user
from app.services.embedder import _get_qdrant
from app.services.query_embedder import embed_query
from app.services.query_processor import normalize_query
from app.services.redis_service import get_redis_client
from app.services.llm_service import build_answer, build_answer_stream, parse_and_filter_results, condense_query, generate_suggested_questions, assemble_context
from app.services.rbac_filter import build_rbac_filter
from app.config.settings import get_settings

from app.routes.search_v1 import (
    _get_visible_doc_ids_for_role,
    _bm25_search,
    _merge_results,
    _rerank_with_cross_encoder,
    RERANK_TOP_K,
    CONFIDENCE_THRESHOLD,
)

import logging

logger = logging.getLogger(__name__)
settings = get_settings()
router = APIRouter(prefix="/api", tags=["chat"])


class ChatRequest(BaseModel):
    query: str
    limit: int = 15
    department: Optional[str] = None
    keyword_backend: Optional[str] = None
    stream: bool = False
    file_type: Optional[str] = None
    date_range: Optional[str] = None
    # Conversation history for follow-up question support
    # Each entry: {"role": "user" | "assistant", "content": "..."}
    history: Optional[list[dict]] = None


def _make_chat_filter(
    role: str,
    user_id: int,
    department: Optional[str],
    file_type: Optional[str] = None,
    date_range: Optional[str] = None,
):
    """Same as the org RBAC filter, but OR'd with an exact owner_id match
    so a user's own personal uploads are also searchable in their chat -
    without making them visible to anyone else, including admins."""
    base = build_rbac_filter(role)
    
    should_conditions = list(base.should) if base.should else []
    should_conditions.append(
        FieldCondition(key="owner_id", match=MatchValue(value=user_id))
    )
    base.should = should_conditions  # type: ignore

    must_conditions = list(base.must) if base.must else []

    if department:
        must_conditions.append(FieldCondition(key="department", match=MatchValue(value=department)))

    if file_type:
        must_conditions.append(FieldCondition(key="file_type", match=MatchValue(value=file_type.lower().strip())))

    if date_range:
        import datetime
        from datetime import timezone
        from qdrant_client.models import Range
        now = datetime.datetime.now(timezone.utc).replace(tzinfo=None)
        delta = None
        if date_range == "today":
            delta = datetime.timedelta(days=1)
        elif date_range == "week":
            delta = datetime.timedelta(days=7)
        elif date_range == "month":
            delta = datetime.timedelta(days=30)
        elif date_range == "year":
            delta = datetime.timedelta(days=365)

        if delta:
            start_time = (now - delta).isoformat()
            must_conditions.append(
                FieldCondition(
                    key="created_at",
                    range=Range(gte=start_time),  # type: ignore
                )
            )

    base.must = must_conditions  # type: ignore
    return base


def normalize_filename(name: str) -> str:
    if not name:
        return ""
    import re
    try:
        b = name.encode('latin-1')
        name = b.decode('cp1252')
    except Exception:
        pass
    name = name.replace('\x96', '-')
    name = name.replace('\u2013', '-')
    name = name.replace('\u2014', '-')
    return re.sub(r'[^a-zA-Z0-9]', '', name).lower()


@router.post("/chat")
def chat(
    req: ChatRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        if not req.query or not req.query.strip():
            raise HTTPException(status_code=400, detail="Query cannot be empty")

        normalized = normalize_query(req.query)
        if not normalized:
            raise HTTPException(status_code=400, detail="Query is empty after normalization")

        # Condense follow-up queries using conversation history so they are
        # self-contained and retrieve the correct documents.
        history_messages = req.history or []
        search_query = req.query
        if history_messages:
            try:
                search_query = condense_query(req.query, history_messages)
                logger.info("Condensed follow-up '%s' -> '%s'", req.query, search_query)
            except Exception as cq_err:
                logger.warning("condense_query failed, using raw query: %s", cq_err)
        normalized_search = normalize_query(search_query) or normalized

        # Check cache (only if NOT streaming)
        import json
        redis_client = get_redis_client()
        cache_key = f"rag_cache:{current_user.role}:{req.department or ''}:{req.file_type or ''}:{req.date_range or ''}:{normalized}"
        
        if not req.stream and redis_client is not None:
            try:
                cached_res = redis_client.get(cache_key)
                if cached_res:
                    import logging
                    logging.getLogger(__name__).info("Serving RAG response from cache")
                    return json.loads(cached_res)
            except Exception as e:
                import logging
                logging.getLogger(__name__).warning(f"Failed to read from RAG cache: {e}")

        # Org-visible docs (role-based) + this user's own personal docs
        visible_doc_ids = _get_visible_doc_ids_for_role(current_user.role, db)
        personal_doc_ids = {
            d.id for d in db.query(Document).filter(Document.owner_user_id == current_user.id).all()
        }
        visible_doc_ids = visible_doc_ids | personal_doc_ids

        query_vector = embed_query(normalized_search)
        if not query_vector:
            raise HTTPException(status_code=400, detail="Empty query vector")

        query_filter = _make_chat_filter(current_user.role, current_user.id, req.department, req.file_type, req.date_range)
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
        bm25_results = _bm25_search(normalized_search, visible_doc_ids, db, top_k=top_k * 2)

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
            filename = r.get("filename")
            doc_id = r.get("document_id")
            doc = None
            if filename:
                norm_q = normalize_filename(filename)
                all_docs = db.query(Document).all()
                for d in all_docs:
                    if normalize_filename(d.original_filename) == norm_q:
                        doc = d
                        break
            if not doc and doc_id and not filename:
                doc = db.query(Document).filter(Document.id == doc_id).first()
                
            if doc:
                r["document_id"] = doc.id
                r["file_path"] = doc.file_path
                r["filename"] = doc.original_filename
                r["department"] = doc.department or r.get("department")
                r["access_level"] = doc.access_level if doc.access_level else r.get("access_level")

            if r.get("chunk_id"):
                chunk_row = db.query(Chunk).filter(Chunk.id == r["chunk_id"]).first()
                if chunk_row:
                    r["full_text"] = chunk_row.text

        # Apply cross-encoder reranking (same as search_v1 main route)
        merged_results = _rerank_with_cross_encoder(normalized, merged_results)

        # After reranking, recompute has_answer using updated scores
        top_score = merged_results[0].get("combined_score", 0) if merged_results else 0
        has_answer = top_score >= CONFIDENCE_THRESHOLD

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
                        "confidence_score": r.get("confidence_score") or r.get("combined_score"),
                        "semantic_score": r.get("semantic_score"),
                        "search_type": r.get("search_type", "hybrid"),
                    })

                yield f"data: {json.dumps({'event': 'metadata', 'results': serializable_results, 'has_answer': has_answer})}\n\n"

                if merged_results:
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
                        for token in build_answer_stream(req.query, context_chunks, history_messages=history_messages):
                            yield f"data: {json.dumps({'event': 'token', 'token': token})}\n\n"
                    except Exception as e:
                        logger.error(f"Streaming LLM failed: {e}")
                        yield f"data: {json.dumps({'event': 'error', 'error': str(e)})}\n\n"

                yield "data: [DONE]\n\n"

            return StreamingResponse(event_generator(), media_type="text/event-stream")

        answer = ""
        # Always attempt to build an answer — the LLM will say "not found" if context is insufficient.
        # This prevents silent empty responses when has_answer is marginally False.
        if merged_results:
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
                answer = build_answer(req.query, context_chunks, history_messages=history_messages)
            except Exception as e:
                logger.error(f"LLM answer generation failed: {e}")
                answer = ""

        # Filter results to only include sources actually cited in the answer
        if answer:
            filtered_results, has_answer_filtered = parse_and_filter_results(answer, merged_results)
            if filtered_results or not has_answer_filtered:
                merged_results = filtered_results
                has_answer = has_answer_filtered

        response_payload = {
            "query": req.query,
            "normalized_query": normalized,
            "role": current_user.role,
            "answer": answer,
            "results": merged_results,
            "has_answer": has_answer,
        }

        if not req.stream and redis_client is not None:
            try:
                redis_client.set(cache_key, json.dumps(response_payload), ex=600)
            except Exception as e:
                logger.warning(f"Failed to write to RAG cache: {e}")

        # Prepare bullet list from answer
        bullets = [line.strip() for line in answer.splitlines() if line.strip().startswith('-')]
        # Ensure at least 5 bullet points – fallback handled in LLM service already
        if len(bullets) < 5:
            # If answer is not already bullet‑formatted, split into sentences and take first few
            import re
            sentences = re.split(r'(?<=[.!?])\s+', answer)
            bullets = [f"- {s.strip()}" for s in sentences if s.strip()][:5]
        # Build context string for suggested questions (use assembled context from chunks)
        context_text = assemble_context(merged_results)
        follow_up_questions = generate_suggested_questions(req.query, answer, context_text)
        response_payload = {
            "query": req.query,
            "normalized_query": normalized,
            "role": current_user.role,
            "answer": answer,
            "bullets": bullets,
            "follow_up_questions": follow_up_questions,
            "results": merged_results,
            "has_answer": has_answer,
        }
        return response_payload
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
