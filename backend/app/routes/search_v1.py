from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from qdrant_client import QdrantClient

from app.config.settings import get_settings
from app.database import SessionLocal, get_db
from app.models import Chunk, User, Document, AccessLevel
from app.services.auth import get_current_user
from app.services.embedder import _get_qdrant
from app.services.query_embedder import embed_query
from app.services.query_processor import normalize_query
from app.services.rbac_filter import build_rbac_filter
from qdrant_client.models import Filter
from rank_bm25 import BM25Okapi
import logging

# Setup logging
logger = logging.getLogger(__name__)

# Confidence threshold used for both:
# - per-result confidence display
# - has_answer (no-answer UI)
CONFIDENCE_THRESHOLD = 0.3

settings = get_settings()
router = APIRouter(prefix="/api", tags=["search"])


class SearchRequest(BaseModel):
    query: str
    limit: int = 10
    offset: int = 0  # pagination offset
    department: Optional[str] = None
    # Optional keyword backend override: "bm25" or "postgres".
    # If omitted, BM25 is used (Postgres full-text can be added later).
    keyword_backend: Optional[str] = None



def _make_filter(role: str, department: Optional[str]) -> Filter:
    base = build_rbac_filter(role)

    if department:
        # Qdrant client expects Filter as pydantic model;
        # we append additional FieldCondition to `must`.
        from qdrant_client.models import FieldCondition, MatchValue

        base.must.append(
            FieldCondition(
                key="department",
                match=MatchValue(value=department),
            )
        )

    return base


def _get_visible_doc_ids_for_role(role: str, db) -> set[int]:
    """Get document IDs visible to user's role based on access_level."""
    role_lower = (role or "").strip().lower()

    # Determine allowed access levels for role
    allowed_levels = set()
    if role_lower in ("admin", "hr"):
        allowed_levels = {AccessLevel.public, AccessLevel.internal, AccessLevel.confidential, AccessLevel.restricted}
    elif role_lower == "manager":
        allowed_levels = {AccessLevel.public, AccessLevel.internal, AccessLevel.confidential}
    else:  # employee
        allowed_levels = {AccessLevel.public, AccessLevel.internal}

    # Get document IDs matching allowed access levels
    docs = db.query(Document).filter(Document.access_level.in_(allowed_levels)).all()
    return {d.id for d in docs}


def _bm25_search(query: str, visible_doc_ids: set[int], db, top_k: int = 10) -> list[dict]:
    """Run BM25 keyword search on chunks from visible documents."""
    if not visible_doc_ids:
        return []

    # Get chunks for visible documents
    chunks = db.query(Chunk).filter(
        Chunk.document_id.in_(visible_doc_ids),
        Chunk.is_embedded == True
    ).all()

    if not chunks:
        return []

    # Tokenize corpus for BM25
    corpus = [c.text.lower().split() for c in chunks]
    bm25 = BM25Okapi(corpus)

    # Tokenize query
    query_tokens = query.lower().split()
    scores = bm25.get_scores(query_tokens)

    # Get top results
    top_indices = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:top_k]

    results = []
    for idx in top_indices:
        if scores[idx] > 0:
            chunk = chunks[idx]
            results.append({
                "chunk_id": chunk.id,
                "document_id": chunk.document_id,
                "chunk_index": chunk.chunk_index,
                "page_number": chunk.page_number,
                "text_preview": chunk.text[:200] if chunk.text else "",
                "bm25_score": scores[idx],
            })

    return results


def _postgres_ts_search(query: str, visible_doc_ids: set[int], db, top_k: int = 10) -> list[dict]:
    """Run PostgreSQL full-text search (tsvector) on chunks from visible documents."""
    from sqlalchemy import text, func
    from sqlalchemy.dialects import postgresql

    if not visible_doc_ids:
        return []

    # Check if using PostgreSQL
    db_url = str(db.bind.url)
    if "postgresql" not in db_url.lower():
        return []  # Fall back to BM25 for SQLite

    try:
        # Build tsquery from query tokens
        query_tokens = query.lower().split()
        ts_query = " & ".join(query_tokens) if query_tokens else ""

        if not ts_query:
            return []

        # Use raw SQL for PostgreSQL full-text search
        sql = text("""
            SELECT id, document_id, chunk_index, page_number, text,
                   ts_rank(to_tsvector('english', text), plainto_tsquery('english', :query)) as rank
            FROM chunks
            WHERE document_id IN :doc_ids
              AND is_embedded = true
              AND to_tsvector('english', text) @@ plainto_tsquery('english', :query)
            ORDER BY rank DESC
            LIMIT :limit
        """)

        # Execute with bound parameters
        result = db.execute(
            sql,
            {
                "query": query,
                "doc_ids": tuple(visible_doc_ids),
                "limit": top_k,
            },
        )

        results = []
        for row in result:
            results.append({
                "chunk_id": row.id,
                "document_id": row.document_id,
                "chunk_index": row.chunk_index,
                "page_number": row.page_number,
                "text_preview": row.text[:200] if row.text else "",
                "bm25_score": float(row.rank),  # Use ts_rank as the score
            })

        return results
    except Exception as e:
        logger.warning(f"PostgreSQL tsvector search failed: {e}, falling back to BM25")
        return []


def _calculate_combined_score(item: dict, semantic_max: float, bm25_max: float) -> float:
    """Re-rank: 0.7×semantic + 0.3×keyword + metadata_boost."""
    semantic = item.get("semantic_score", 0)
    bm25 = item.get("bm25_score", 0)

    # Normalize scores to 0-1 range
    sem_norm = semantic / semantic_max if semantic_max > 0 else 0
    bm25_norm = min(bm25 / 10, 1.0)  # BM25 scores vary, cap at 10 for normalization

    # Base score: weighted combination
    base_score = 0.7 * sem_norm + 0.3 * bm25_norm

    # Metadata boost: boost higher access levels
    meta_boost = 0.0
    access_level = item.get("access_level", "")
    if access_level == "internal":
        meta_boost = 0.05
    elif access_level == "confidential":
        meta_boost = 0.08
    elif access_level == "restricted":
        meta_boost = 0.1

    return base_score + meta_boost


def _merge_results(
    semantic_hits: list,
    bm25_results: list[dict],
    top_k: int,
    confidence_threshold: float = CONFIDENCE_THRESHOLD,
) -> tuple[list[dict], bool]:
    """Merge and re-rank with confidence threshold. Returns (results, has_answer)."""
    # Get max scores for normalization
    semantic_max = max((h.score for h in semantic_hits), default=0)
    bm25_max = max((b.get("bm25_score", 0) for b in bm25_results), default=0)

    seen = set()
    merged = []

    # Interleave and collect all candidates
    semantic_idx = 0
    bm25_idx = 0

    while semantic_idx < len(semantic_hits) or bm25_idx < len(bm25_results):
        if semantic_idx < len(semantic_hits):
            h = semantic_hits[semantic_idx]
            chunk_id = h.payload.get("chunk_id") if h.payload else None
            if chunk_id and chunk_id not in seen:
                seen.add(chunk_id)
                merged.append({
                    "score": h.score,
                    "semantic_score": h.score,
                    "qdrant_point_id": h.id,
                    "chunk_id": chunk_id,
                    "document_id": h.payload.get("document_id") if h.payload else None,
                    "chunk_index": h.payload.get("chunk_index") if h.payload else None,
                    "page_number": h.payload.get("page_number") if h.payload else None,
                    "text_preview": h.payload.get("text_preview") if h.payload else "",
                    "department": h.payload.get("department") if h.payload else None,
                    "access_level": h.payload.get("access_level") if h.payload else None,
                    "filename": h.payload.get("filename") if h.payload else None,
                    "search_type": "semantic",
                })
            semantic_idx += 1
            continue

        if bm25_idx < len(bm25_results):
            b = bm25_results[bm25_idx]
            chunk_id = b.get("chunk_id")
            if chunk_id and chunk_id not in seen:
                seen.add(chunk_id)
                merged.append({
                    "score": b.get("bm25_score", 0),
                    "semantic_score": 0,
                    "bm25_score": b.get("bm25_score", 0),
                    "chunk_id": chunk_id,
                    "document_id": b.get("document_id"),
                    "chunk_index": b.get("chunk_index"),
                    "page_number": b.get("page_number"),
                    "text_preview": b.get("text_preview", ""),
                    "department": b.get("department"),
                    "access_level": b.get("access_level"),
                    "filename": b.get("filename"),
                    "search_type": "bm25",
                })
            bm25_idx += 1
            continue

        break

    # Calculate combined scores with re-ranking
    for m in merged:
        m["combined_score"] = _calculate_combined_score(m, semantic_max, bm25_max)

    # Sort by combined score descending
    merged.sort(key=lambda x: x.get("combined_score", 0), reverse=True)

    results = merged[:top_k]

    # Confidence per result (0..1 approx). We treat combined_score as confidence.
    # (If you later change scoring normalization, update here.)
    for r in results:
        combined = r.get("combined_score", 0) or 0
        r["confidence_score"] = float(combined)

    # Check confidence threshold
    top_score = results[0].get("confidence_score", 0) if results else 0
    has_answer = top_score >= confidence_threshold

    return results if has_answer else [], has_answer


@router.post("/search")
def search(
    req: SearchRequest,
    current_user: User = Depends(get_current_user),
    db: SessionLocal = Depends(get_db),  # Add db dependency
):
    try:
        if req.limit < 1 or req.limit > 50:
            raise HTTPException(status_code=400, detail="limit must be between 1 and 50")
        if not req.query or not req.query.strip():
            raise HTTPException(status_code=400, detail="Query cannot be empty")

        normalized = normalize_query(req.query)
        if not normalized:
            raise HTTPException(status_code=400, detail="Query is empty after normalization")

        # Get document IDs visible to user's role
        visible_doc_ids = _get_visible_doc_ids_for_role(str(current_user.role), db)

        # 1) Semantic search in Qdrant (cosine similarity)
        query_vector = embed_query(normalized)
        if not query_vector:
            raise HTTPException(status_code=400, detail="Empty query vector")

        query_filter = _make_filter(str(current_user.role), req.department)
        client: QdrantClient = _get_qdrant()

        top_k = req.limit

        # 1) Semantic search in Qdrant (cosine similarity) - Top-K
        semantic_hits = client.search(
            collection_name=settings.qdrant_collection_name,
            query_vector=query_vector,
            query_filter=query_filter,
            limit=top_k,
            with_payload=True,
        )

        # 2) Keyword search in database - Top-K
        keyword_backend = (req.keyword_backend or "bm25").strip().lower()
        if keyword_backend not in {"bm25", "postgres"}:
            raise HTTPException(status_code=400, detail="keyword_backend must be 'bm25' or 'postgres'")

        # Use PostgreSQL tsvector if postgres selected and available, else fallback to BM25
        if keyword_backend == "postgres":
            ts_results = _postgres_ts_search(normalized, visible_doc_ids, db, top_k=top_k * 2)
            bm25_results = ts_results if ts_results else _bm25_search(normalized, visible_doc_ids, db, top_k=top_k * 2)
        else:
            bm25_results = _bm25_search(normalized, visible_doc_ids, db, top_k=top_k * 2)


        # Get documents info for BM25 results
        for b in bm25_results:
            if b.get("document_id"):
                doc = db.query(Document).filter(Document.id == b["document_id"]).first()
                if doc:
                    b["department"] = doc.department
                    b["access_level"] = doc.access_level
                    b["filename"] = doc.original_filename

        # 3) Merge + dedup + final Top-K=10 (or req.limit) unified candidate list
        merged_results, has_answer = _merge_results(
            semantic_hits,
            bm25_results,
            top_k=top_k,
            confidence_threshold=CONFIDENCE_THRESHOLD,
        )

        # Enrich merged results with full source attribution:
        # doc name + doc_id + chunk_id + page + path
        #
        # Note: Qdrant payload might not always contain filename/path reliably,
        # so we fetch from DB based on document_id.
        doc_ids = {r.get("document_id") for r in merged_results if r.get("document_id") is not None}
        docs_by_id = {}
        if doc_ids:
            docs = db.query(Document).filter(Document.id.in_(tuple(doc_ids))).all()
            docs_by_id = {d.id: d for d in docs}

        for r in merged_results:
            doc_id = r.get("document_id")
            doc = docs_by_id.get(doc_id) if doc_id is not None else None
            if doc:
                r["doc_id"] = doc.id
                # doc_name: keep consistent with UI usage (use original_filename)
                r["doc_name"] = doc.original_filename or doc.filename
                r["path"] = doc.file_path
                # Keep backwards-compatible filename field too
                r["filename"] = doc.original_filename or doc.filename
            else:
                # Best-effort fallback from any existing fields
                r["doc_id"] = r.get("document_id")
                r["doc_name"] = r.get("filename")
                # path may be missing if DB enrichment fails
                r["path"] = r.get("path")

            # Ensure chunk_id/page fields match requested names/types
            r["chunk_id"] = r.get("chunk_id")
            r["page"] = r.get("page_number")

        return {
            "query": req.query,
            "normalized_query": normalized,
            "role": current_user.role,
            "results": merged_results,
            "has_answer": has_answer,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

