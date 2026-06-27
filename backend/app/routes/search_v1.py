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


settings = get_settings()
router = APIRouter(prefix="/api", tags=["search"])


class SearchRequest(BaseModel):
    query: str
    limit: int = 10
    offset: int = 0
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
    semantic_hits: list, bm25_results: list[dict], top_k: int, confidence_threshold: float = 0.72
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

    # Check confidence threshold
    top_score = results[0].get("combined_score", 0) if results else 0
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

        bm25_results = _bm25_search(normalized, visible_doc_ids, db, top_k=top_k * 2)

        # Postgres full-text (tsvector) not implemented yet; fall back to BM25.
        if keyword_backend == "postgres":
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
            confidence_threshold=0.72,
        )

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

