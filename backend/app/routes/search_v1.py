from typing import Optional, Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException, Request
from app.services.limiter import limiter
from pydantic import BaseModel
from qdrant_client import QdrantClient
from qdrant_client.models import Filter
from sqlalchemy.orm import Session
import logging

from app.config.settings import get_settings
from app.database import get_db
from app.models import Chunk, User, Document, AccessLevel
from app.services.auth import get_current_user
from app.services.embedder import _get_qdrant
from app.services.llm_service import build_answer, parse_and_filter_results
from app.services.query_embedder import embed_query
from app.services.query_processor import normalize_query
from app.services.rbac_filter import build_rbac_filter

logger = logging.getLogger(__name__)

settings = get_settings()
router = APIRouter(prefix="/api", tags=["search"])

# Phase 4.3 spec: keep top 5 after re-ranking, regardless of retrieval limit
RERANK_TOP_K = 5
CONFIDENCE_THRESHOLD = 0.55

_reranker = None

def _get_reranker():
    global _reranker
    if _reranker is None:
        try:
            from fastembed.rerank.cross_encoder import TextCrossEncoder
            import os
            cache_dir = os.environ.get("FASTEMBED_CACHE_PATH") or "./fastembed_cache"
            os.makedirs(cache_dir, exist_ok=True)
            _reranker = TextCrossEncoder("Xenova/ms-marco-MiniLM-L-6-v2", cache_dir=cache_dir)
        except Exception as e:
            logger.warning("Failed to initialize TextCrossEncoder: %s", e)
    return _reranker


def _rerank_with_cross_encoder(query: str, merged_results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    if not merged_results:
        return []
    encoder = _get_reranker()
    if not encoder:
        return merged_results
    try:
        # Use full text for reranking to avoid keyword dilution in truncated previews
        texts = [r.get("text") or r.get("parent_text") or r.get("text_preview", "") for r in merged_results]
        scores = list(encoder.rerank(query, texts))
        for idx, score in enumerate(scores):
            import math
            # Temperature scaling T=2.8 for cross-encoder logits with +12.0 bias shift to align with model output distribution
            ce_prob = 1.0 / (1.0 + math.exp(-(score + 12.0) / 2.8))
            sem = float(merged_results[idx].get("semantic_score", 0.0) or 0.0)
            final_score = 0.6 * ce_prob + 0.4 * sem
 
            # Cap score at 0.98 to prevent flat 100%/99% saturation
            final_score = min(0.98, max(0.05, final_score))
            final_score = round(final_score, 4)
 
            merged_results[idx]["combined_score"] = final_score
            merged_results[idx]["confidence_score"] = final_score
            merged_results[idx]["rerank_score"] = score
        merged_results.sort(key=lambda x: x.get("combined_score", 0), reverse=True)
    except Exception as e:
        logger.warning("Cross-encoder reranking failed: %s", e)
    return merged_results

def expand_query(query: str) -> List[str]:
    return [query]  # TEMP: LLM expansion disabled -- was burning quota + causing topic drift
    try:
        from app.services.llm_service import LLMService
        llm = LLMService(temperature=0.3)
        prompt = (
            "Given the following user search query, generate 2 variations of this query that use different synonyms or phrasing to search for similar documents.\n"
            "Output only the variations, one per line, no numbering or other text.\n\n"
            f"Query: {query}"
        )
        res = llm.chat_completion([{"role": "user", "content": prompt}], max_tokens=100)
        variations = [line.strip() for line in res.split("\n") if line.strip()]
        cleaned = [query]
        for v in variations:
            v_clean = v.strip("-*\"'").strip()
            if v_clean and v_clean not in cleaned:
                cleaned.append(v_clean)
        return cleaned[:3]
    except Exception as e:
        logger.warning("Query expansion failed, using original query: %s", e)
        return [query]


class SearchRequest(BaseModel):
    query: str
    limit: int = 15
    offset: int = 0
    department: Optional[str] = None
    keyword_backend: Optional[str] = None
    file_type: Optional[str] = None
    date_range: Optional[str] = None
    document_ids: Optional[List[int]] = None


ChatRequest = SearchRequest


def _make_filter(
    role: str,
    department: Optional[str],
    file_type: Optional[str] = None,
    date_range: Optional[str] = None,
    user_id: Optional[int] = None,
    document_ids: Optional[list[int]] = None,
) -> Filter:
    base = build_rbac_filter(role)
    from qdrant_client.models import FieldCondition, MatchValue, Range
    import datetime

    should_conditions = list(base.should) if base.should else []
    if user_id is not None:
        should_conditions.append(
            FieldCondition(key="owner_id", match=MatchValue(value=user_id))
        )
    base.should = should_conditions  # type: ignore

    must_not_conditions = list(base.must_not) if base.must_not else []
    must_not_conditions.append(
        FieldCondition(
            key="is_active",
            match=MatchValue(value=False),
        )
    )
    base.must_not = must_not_conditions  # type: ignore

    must_conditions = list(base.must) if base.must else []

    if document_ids:
        from qdrant_client.models import MatchAny
        must_conditions.append(
            FieldCondition(
                key="document_id",
                match=MatchAny(any=list(document_ids)),
            )
        )

    if department:
        must_conditions.append(
            FieldCondition(
                key="department",
                match=MatchValue(value=department),
            )
        )

    if file_type:
        must_conditions.append(
            FieldCondition(
                key="file_type",
                match=MatchValue(value=file_type.lower().strip()),
            )
        )

    if date_range:
        from datetime import timezone
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


def _get_visible_doc_ids_for_role(role: str, db) -> set[int]:
    """Get document IDs visible to user's role based on access_level."""
    role_lower = (role or "").strip().lower()
    allowed_levels = set()
    if role_lower in ("admin", "hr"):
        allowed_levels = {AccessLevel.public, AccessLevel.internal, AccessLevel.confidential, AccessLevel.restricted}
    elif role_lower == "manager":
        allowed_levels = {AccessLevel.public, AccessLevel.internal, AccessLevel.confidential}
    else:
        allowed_levels = {AccessLevel.public, AccessLevel.internal}
    docs = db.query(Document).filter(
        Document.access_level.in_(allowed_levels),
        Document.is_active == True
    ).all()
    return {d.id for d in docs}


try:
    from rank_bm25 import BM25Okapi  # type: ignore[import-not-found]
except ImportError:  # pragma: no cover
    BM25Okapi = None


def _bm25_search(query: str, visible_doc_ids: set[int], db, top_k: int = 10) -> List[Dict[str, Any]]:
    """Run a lightweight keyword search over chunks from visible documents."""
    if not visible_doc_ids:
        return []

    chunks = (
        db.query(Chunk)
        .filter(
            Chunk.document_id.in_(visible_doc_ids),
        )
        .all()
    )

    if not chunks:
        return []

    query_tokens = {token for token in query.lower().split() if token}
    if not query_tokens:
        return []

    if BM25Okapi is not None:
        corpus = [c.text.lower().split() for c in chunks]
        bm25 = BM25Okapi(corpus)
        
        # Filter out common stop words and search query triggers to make keyword match highly specific
        stop_words = {
            "what", "is", "are", "the", "a", "an", "of", "in", "to", "for", "with", "on", "at", "by", "from", "do", "play", "how", "why", "show", "key", "points", "summarize", "sources", "document", "documents"
        }
        query_tokens_list = [token for token in query.lower().split() if token and token not in stop_words]
        if not query_tokens_list:
            query_tokens_list = [token for token in query.lower().split() if token]
            
        scores = bm25.get_scores(query_tokens_list)
        top_indices = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:top_k]

        results = []
        for idx in top_indices:
            if scores[idx] > 0:
                chunk = chunks[idx]
                results.append(
                    {
                        "chunk_id": chunk.id,
                        "document_id": chunk.document_id,
                        "chunk_index": chunk.chunk_index,
                        "page_number": chunk.page_number,
                        "text_preview": chunk.text[:200] if chunk.text else "",
                        "bm25_score": float(scores[idx]),
                    }
                )
        return results

    results = []
    for chunk in chunks:
        text_tokens = {token for token in (chunk.text or "").lower().split() if token}
        overlap = len(query_tokens & text_tokens)
        if overlap > 0:
            results.append(
                {
                    "chunk_id": chunk.id,
                    "document_id": chunk.document_id,
                    "chunk_index": chunk.chunk_index,
                    "page_number": chunk.page_number,
                    "text_preview": chunk.text[:200] if chunk.text else "",
                    "bm25_score": float(overlap),
                }
            )

    results.sort(key=lambda item: item.get("bm25_score", 0), reverse=True)
    return results[:top_k]


def _postgres_ts_search(query: str, visible_doc_ids: set[int], db, top_k: int = 10) -> List[Dict[str, Any]]:
    """Run PostgreSQL full-text search (tsvector) on chunks from visible documents."""
    from sqlalchemy import text, bindparam

    if not visible_doc_ids:
        return []

    db_url = str(db.bind.url)
    if "postgresql" not in db_url.lower():
        return []

    try:
        query_tokens = query.lower().split()
        ts_query = " & ".join(query_tokens) if query_tokens else ""

        if not ts_query:
            return []

        sql = text(
            """
            SELECT id, document_id, chunk_index, page_number, text,
                   ts_rank(to_tsvector('english', text), plainto_tsquery('english', :query)) as rank
            FROM chunks
            WHERE document_id IN :doc_ids
              AND is_embedded = true
              AND to_tsvector('english', text) @@ plainto_tsquery('english', :query)
            ORDER BY rank DESC
            LIMIT :limit
            """
        ).bindparams(bindparam("doc_ids", expanding=True))

        result = db.execute(
            sql,
            {
                "query": query,
                "doc_ids": list(visible_doc_ids),
                "limit": top_k,
            },
        )

        results = []
        for row in result:
            results.append(
                {
                    "chunk_id": row.id,
                    "document_id": row.document_id,
                    "chunk_index": row.chunk_index,
                    "page_number": row.page_number,
                    "text_preview": row.text[:200] if row.text else "",
                    "bm25_score": float(row.rank),
                }
            )

        return results
    except Exception as e:
        logger.warning(f"PostgreSQL tsvector search failed: {e}, falling back to BM25")
        return []


def _calculate_combined_score(item: dict, semantic_max: float, bm25_max: float) -> float:
    """Re-rank: 0.7x semantic + 0.3x keyword + metadata_boost."""
    semantic = item.get("semantic_score", 0)
    bm25 = item.get("bm25_score", 0)

    sem_norm = semantic / semantic_max if semantic_max > 0 else 0
    bm25_norm = min(bm25 / 10, 1.0)

    base_score = 0.7 * sem_norm + 0.3 * bm25_norm

    meta_boost = 0.0
    access_level = item.get("access_level", "")
    if access_level == "internal":
        meta_boost = 0.05
    elif access_level == "confidential":
        meta_boost = 0.08
    elif access_level == "restricted":
        meta_boost = 0.1

    return min(base_score + meta_boost, 1.0)


def _merge_results(
    semantic_hits: list,
    bm25_results: list[dict],
    top_k: int,
    confidence_threshold: float = CONFIDENCE_THRESHOLD,
) -> tuple[list[dict], bool]:
    """Merge and re-rank with Reciprocal Rank Fusion (RRF) and metadata boosts. Returns (results, has_answer)."""
    # 1. Map chunk_id to ranks (1-indexed)
    semantic_ranks = {}
    for rank, h in enumerate(semantic_hits, 1):
        chunk_id = h.payload.get("chunk_id") if h.payload else None
        if chunk_id:
            semantic_ranks[chunk_id] = rank

    bm25_ranks = {}
    for rank, b in enumerate(bm25_results, 1):
        chunk_id = b.get("chunk_id")
        if chunk_id:
            bm25_ranks[chunk_id] = rank

    # Constant k for RRF
    k = 60
    # Max possible RRF score with k=60 (if item ranks first in both lists) is 1/61 + 1/61
    max_possible_rrf = (1.0 / (k + 1)) * 2

    seen = set()
    merged: list[dict] = []

    def get_rrf(cid):
        sem_rank = semantic_ranks.get(cid)
        bm_rank = bm25_ranks.get(cid)
        score = 0.0
        if sem_rank is not None:
            score += 1.0 / (k + sem_rank)
        if bm_rank is not None:
            score += 1.0 / (k + bm_rank)
        return score

    semantic_idx = 0
    bm25_idx = 0

    while semantic_idx < len(semantic_hits) or bm25_idx < len(bm25_results):
        if semantic_idx < len(semantic_hits):
            h = semantic_hits[semantic_idx]
            chunk_id = h.payload.get("chunk_id") if h.payload else None
            if chunk_id and chunk_id not in seen:
                seen.add(chunk_id)
                rrf_val = get_rrf(chunk_id)
                merged.append(
                    {
                        "score": h.score,
                        "semantic_score": h.score,
                        "bm25_score": 0.0,
                        "qdrant_point_id": h.id,
                        "chunk_id": chunk_id,
                        "document_id": h.payload.get("document_id") if h.payload else None,
                        "chunk_index": h.payload.get("chunk_index") if h.payload else None,
                        "page_number": h.payload.get("page_number") if h.payload else None,
                        "text_preview": h.payload.get("text_preview") if h.payload else "",
                        "department": h.payload.get("department") if h.payload else None,
                        "access_level": h.payload.get("access_level") if h.payload else None,
                        "filename": h.payload.get("filename") if h.payload else None,
                        "search_type": "hybrid",
                        "rrf_score": rrf_val,
                    }
                )
            semantic_idx += 1
            continue

        if bm25_idx < len(bm25_results):
            b = bm25_results[bm25_idx]
            chunk_id = b.get("chunk_id")
            if chunk_id and chunk_id not in seen:
                seen.add(chunk_id)
                rrf_val = get_rrf(chunk_id)
                merged.append(
                    {
                        "score": b.get("bm25_score", 0),
                        "semantic_score": 0.0,
                        "bm25_score": b.get("bm25_score", 0),
                        "chunk_id": chunk_id,
                        "document_id": b.get("document_id"),
                        "chunk_index": b.get("chunk_index"),
                        "page_number": b.get("page_number"),
                        "text_preview": b.get("text_preview", ""),
                        "department": b.get("department"),
                        "access_level": b.get("access_level"),
                        "filename": b.get("filename"),
                        "search_type": "hybrid",
                        "rrf_score": rrf_val,
                    }
                )
            bm25_idx += 1
            continue

        break

    for m in merged:
        cid = m["chunk_id"]
        sem_score = float(m.get("semantic_score", 0.0) or 0.0)

        if sem_score > 0:
            base_score = sem_score
            if cid in bm25_ranks:
                bm25_rank = bm25_ranks[cid]
                bm25_boost = max(0.0, 0.08 * (1.0 - (bm25_rank - 1) / max(len(bm25_results), 1)))
                base_score = min(0.98, base_score + bm25_boost)
        else:
            bm25_rank = bm25_ranks.get(cid, len(bm25_results) + 1)
            # Cap keyword-only match score at 0.50 so it doesn't override semantic matches
            base_score = max(0.20, 0.50 - (bm25_rank - 1) * 0.05)

        meta_boost = 0.0
        access_level = m.get("access_level", "")
        if access_level == "internal":
            meta_boost = 0.02
        elif access_level == "confidential":
            meta_boost = 0.03
        elif access_level == "restricted":
            meta_boost = 0.04

        final_combined = round(min(0.98, base_score + meta_boost), 4)
        m["combined_score"] = final_combined
        m["confidence_score"] = final_combined

    merged.sort(key=lambda x: x.get("combined_score", 0), reverse=True)

    results = merged[:top_k]

    top_score = results[0].get("combined_score", 0) if results else 0
    has_answer = top_score >= confidence_threshold

    # Always return results so callers (chat, reranker) have chunks to work with.
    # has_answer is a confidence signal; callers decide whether to use the answer.
    return results, has_answer


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


def search(
    req: SearchRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        if req.limit < 1 or req.limit > 50:
            raise HTTPException(status_code=400, detail="limit must be between 1 and 50")
        if not req.query or not req.query.strip():
            raise HTTPException(status_code=400, detail="Query cannot be empty")

        normalized = normalize_query(req.query)
        if not normalized:
            raise HTTPException(status_code=400, detail="Query is empty after normalization")

        # Check semantic cache
        from app.models import SemanticCache
        import json
        import math
        
        def cosine_similarity(v1: list[float], v2: list[float]) -> float:
            dot_prod = sum(a * b for a, b in zip(v1, v2))
            magnitude1 = math.sqrt(sum(a * a for a in v1))
            magnitude2 = math.sqrt(sum(b * b for b in v2))
            if magnitude1 == 0 or magnitude2 == 0:
                return 0.0
            return dot_prod / (magnitude1 * magnitude2)

        # Generate embedding vector for cache lookup
        query_vector = embed_query(normalized)
        if query_vector and not req.document_ids and not req.department and not req.file_type and not req.date_range:
            cache_entries = db.query(SemanticCache).filter(SemanticCache.role == current_user.role).all()
            best_match = None
            best_sim = -1.0
            for entry in cache_entries:
                try:
                    entry_embedding = json.loads(entry.embedding_json)
                    sim = cosine_similarity(query_vector, entry_embedding)
                    if sim > best_sim:
                        best_sim = sim
                        best_match = entry
                except Exception:
                    continue
            
            if best_match and best_sim >= 0.96:
                logger.info("Semantic cache HIT (similarity: %s) for query: '%s'", best_sim, req.query)
                try:
                    cached_res = json.loads(best_match.response_json)
                    cached_res["query"] = req.query
                    return cached_res
                except Exception:
                    pass

        visible_doc_ids = _get_visible_doc_ids_for_role(current_user.role, db)
        personal_doc_ids = {
            d.id for d in db.query(Document).filter(
                Document.owner_user_id == current_user.id,
                Document.is_active == True
            ).all()
        }
        allowed_doc_ids = visible_doc_ids | personal_doc_ids

        if req.document_ids:
            visible_doc_ids = set(req.document_ids) & allowed_doc_ids
        else:
            visible_doc_ids = allowed_doc_ids

        # Query Expansion
        expanded_queries = expand_query(req.query)

        query_filter = _make_filter(
            current_user.role,
            req.department,
            req.file_type,
            req.date_range,
            user_id=current_user.id,
            document_ids=list(visible_doc_ids)
        )
        top_k = req.limit

        semantic_hits: list[Any] = []
        seen_points = set()
        try:
            client: QdrantClient = _get_qdrant()
            for eq in expanded_queries:
                eq_normalized = normalize_query(eq)
                if not eq_normalized:
                    continue
                eq_vector = embed_query(eq_normalized)
                if not eq_vector:
                    continue
                try:
                    hits = client.query_points(
                        collection_name=settings.qdrant_collection_name,
                        query=eq_vector,
                        query_filter=query_filter,
                        limit=top_k,
                        with_payload=True,
                    ).points
                except Exception as conn_err:
                    logger.warning("Qdrant query failed, attempting auto-reconnect: %s", conn_err)
                    client = _get_qdrant(force_reconnect=True)
                    hits = client.query_points(
                        collection_name=settings.qdrant_collection_name,
                        query=eq_vector,
                        query_filter=query_filter,
                        limit=top_k,
                        with_payload=True,
                    ).points

                for hit in hits:
                    if hit.id not in seen_points:
                        seen_points.add(hit.id)
                        semantic_hits.append(hit)
        except Exception as exc:
            logger.warning("Qdrant semantic search failed: %s", exc)

        keyword_backend = (req.keyword_backend or "bm25").strip().lower()
        if keyword_backend not in {"bm25", "postgres"}:
            raise HTTPException(status_code=400, detail="keyword_backend must be 'bm25' or 'postgres'")

        if keyword_backend == "postgres":
            ts_results = _postgres_ts_search(normalized, visible_doc_ids, db, top_k=top_k * 2)
            bm25_results = ts_results if ts_results else _bm25_search(normalized, visible_doc_ids, db, top_k=top_k * 2)
        else:
            bm25_results = _bm25_search(normalized, visible_doc_ids, db, top_k=top_k * 2)

        for b in bm25_results:
            if b.get("document_id"):
                doc = db.query(Document).filter(Document.id == b["document_id"]).first()
                if doc:
                    b["department"] = doc.department
                    b["access_level"] = doc.access_level
                    b["filename"] = doc.original_filename

        # Hybrid merge candidates (collect more for Cross-Encoder)
        merged_results, _ = _merge_results(
            semantic_hits,
            bm25_results,
            top_k=RERANK_TOP_K * 2,
            confidence_threshold=0.0,
        )

        # Source attribution & enrichment: resolve documents and chunks correctly from active SQLite DB
        # Run on the merge candidates first so that the Cross-Encoder has access to full texts
        for r in merged_results:
            doc_id = r.get("document_id")
            filename = r.get("filename")
            doc = None
            
            # 1. Match document by normalized original filename first to bypass SQLite/Qdrant ID discrepancies
            if filename:
                norm_q = normalize_filename(filename)
                all_docs = db.query(Document).all()
                for d in all_docs:
                    if normalize_filename(d.original_filename) == norm_q:
                        doc = d
                        break
            # 2. DO NOT fall back to doc_id if filename is present but failed to match (stale Qdrant document)
            # Only fall back to doc_id if filename is completely empty/missing
            if not doc and doc_id and not filename:
                doc = db.query(Document).filter(Document.id == doc_id).first()
                
            if doc:
                r["document_id"] = doc.id
                r["file_path"] = doc.file_path
                r["doc_name"] = doc.original_filename
                r["filename"] = doc.original_filename
                r["department"] = doc.department or r.get("department")
                r["access_level"] = doc.access_level if doc.access_level else r.get("access_level")
                if doc.drive_file_id:
                    r["drive_file_id"] = doc.drive_file_id
                    r["drive_url"] = f"https://drive.google.com/file/d/{doc.drive_file_id}/view"
            
            # 3. Match chunk by chunk_index within the matched document
            chunk_id = r.get("chunk_id")
            chunk_index = r.get("chunk_index")
            chunk = None
            if doc and chunk_index is not None:
                chunk = db.query(Chunk).filter(Chunk.document_id == doc.id, Chunk.chunk_index == chunk_index).first()
            # 4. Fall back to chunk_id if chunk_index lookup fails
            if not chunk and chunk_id:
                chunk = db.query(Chunk).filter(Chunk.id == chunk_id).first()
                
            if chunk:
                r["chunk_id"] = chunk.id
                r["text"] = chunk.parent_text if chunk.parent_text else chunk.text
                r["parent_text"] = chunk.parent_text
                r["text_preview"] = chunk.text[:200]
            else:
                # Keep Qdrant payload text if not found in SQLite
                if not r.get("text"):
                    r["text"] = r.get("parent_text") or r.get("text_preview") or ""
                if not r.get("text_preview") and r.get("text"):
                    r["text_preview"] = r["text"][:200]

        # Cross-Encoder Reranking
        # Rerank only the top 8 candidates using the lightweight cross-encoder to prevent CPU timeouts
        rerank_candidates = merged_results[:8]
        other_candidates = merged_results[8:]
        reranked = _rerank_with_cross_encoder(req.query, rerank_candidates)
        merged_results = reranked + other_candidates
        merged_results = merged_results[:req.limit]
        
        top_score = merged_results[0].get("combined_score", 0) if merged_results else 0
        has_answer = top_score >= CONFIDENCE_THRESHOLD

        logger.warning(f"RAG DEBUG | top_score={top_score} threshold={CONFIDENCE_THRESHOLD} has_answer={has_answer}")
        logger.warning(f"RAG DEBUG | retrieved_chunks={len(merged_results)}")


        logger.info("========== RAG DEBUG ==========")
        logger.info("Top score: %s", top_score)
        logger.info("Threshold: %s", CONFIDENCE_THRESHOLD)
        logger.info("Has answer: %s", has_answer)
        logger.info("Retrieved chunks: %s", len(merged_results))
        for r in merged_results:
            logger.info("%s | %s", r.get("filename"), r.get("combined_score"))
        logger.info("===============================")

        if not merged_results:
            # Fall back to visible chunks from the database when vector retrieval yields nothing.
            fallback_chunks = (
                db.query(Chunk)
                .join(Document)
                .filter(
                    Chunk.document_id.in_(visible_doc_ids),
                )
                .order_by(Chunk.document_id, Chunk.chunk_index)
                .limit(top_k)
                .all()
            )
            for chunk in fallback_chunks:
                doc = chunk.document
                merged_results.append(
                    {
                        "score": 0.5,
                        "semantic_score": 0,
                        "bm25_score": 0.5,
                        "chunk_id": chunk.id,
                        "document_id": chunk.document_id,
                        "chunk_index": chunk.chunk_index,
                        "page_number": chunk.page_number,
                        "text_preview": (chunk.text or "")[:200],
                        "department": doc.department if doc is not None else None,
                        "access_level": doc.access_level if (doc is not None and doc.access_level) else None,
                        "filename": doc.original_filename if doc is not None else None,
                        "file_path": doc.file_path if doc is not None else None,
                        "doc_name": doc.original_filename if doc is not None else None,
                        "search_type": "bm25",
                        "text": chunk.text,
                        "parent_text": chunk.parent_text,
                    }
                )

        if merged_results:
            merged_results = merged_results[:top_k]
            seen_files = {}
            deduped = []
            for r in merged_results:
                fname = r.get("filename") or r.get("doc_name") or ""
                score = r.get("combined_score") or r.get("semantic_score") or 0
                if fname not in seen_files or score > seen_files.get(fname, 0):
                    seen_files[fname] = score
                    deduped.append(r)
            merged_results = deduped

        answer = ""
        if merged_results:
            try:
                answer = build_answer(req.query, merged_results[:10])
            except Exception as e:
                logger.error("LLM answer generation failed: %s", e)
                answer = ""

        # Filter results to only include sources actually cited in the answer
        if answer:
            filtered_results, has_answer_filtered = parse_and_filter_results(answer, merged_results)
            if filtered_results or not has_answer_filtered:
                merged_results = filtered_results
                has_answer = has_answer_filtered
            # else: keep original merged_results if filter removed everything

        res_payload = {
            "query": req.query,
            "normalized_query": normalized,
            "role": current_user.role,
            "results": merged_results,
            "has_answer": has_answer,
            "answer": answer,
        }

        # Save to semantic cache
        if query_vector and answer and not req.document_ids and not req.department and not req.file_type and not req.date_range:
            try:
                new_cache = SemanticCache(
                    query=req.query,
                    embedding_json=json.dumps(query_vector),
                    response_json=json.dumps(res_payload),
                    role=current_user.role
                )
                db.add(new_cache)
                db.commit()
            except Exception as cache_save_err:
                logger.warning("Failed to save semantic cache: %s", cache_save_err)

        return res_payload
    except HTTPException:
        raise
    except Exception as e:
        # Preserve original behavior: 500 with error detail (for debugging)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/search")
@limiter.limit("20 per minute")
def search_endpoint(
    req: SearchRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return search(req, current_user=current_user, db=db)


@router.post("/chat")
def chat(
    req: ChatRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return search(req, current_user=current_user, db=db)


