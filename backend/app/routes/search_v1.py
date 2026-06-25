from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from qdrant_client import QdrantClient

from app.config.settings import get_settings
from app.models import User
from app.services.auth import get_current_user
from app.services.embedder import _get_qdrant
from app.services.query_embedder import embed_query
from app.services.query_processor import normalize_query
from app.services.rbac_filter import build_rbac_filter
from qdrant_client.models import Filter

settings = get_settings()
router = APIRouter(prefix="/api", tags=["search"])


class SearchRequest(BaseModel):
    query: str
    limit: int = 5
    department: Optional[str] = None


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


@router.post("/search")
def search(
    req: SearchRequest,
    current_user: User = Depends(get_current_user),
):
    try:
        if req.limit < 1 or req.limit > 50:
            raise HTTPException(status_code=400, detail="limit must be between 1 and 50")
        if not req.query or not req.query.strip():
            raise HTTPException(status_code=400, detail="Query cannot be empty")

        normalized = normalize_query(req.query)
        if not normalized:
            raise HTTPException(status_code=400, detail="Query is empty after normalization")

        query_vector = embed_query(normalized)
        if not query_vector:
            raise HTTPException(status_code=400, detail="Empty query vector")

        query_filter = _make_filter(str(current_user.role), req.department)
        client: QdrantClient = _get_qdrant()

        hits = client.search(
            collection_name=settings.qdrant_collection_name,
            query_vector=query_vector,
            query_filter=query_filter,
            limit=req.limit,
            with_payload=True,
        )

        return {
            "query": req.query,
            "normalized_query": normalized,
            "role": current_user.role,
            "results": [
                {
                    "score": h.score,
                    "qdrant_point_id": h.id,
                    "chunk_id": (h.payload or {}).get("chunk_id"),
                    "document_id": (h.payload or {}).get("document_id"),
                    "chunk_index": (h.payload or {}).get("chunk_index"),
                    "page_number": (h.payload or {}).get("page_number"),
                    "text_preview": (h.payload or {}).get("text_preview"),
                    "department": (h.payload or {}).get("department"),
                    "access_level": (h.payload or {}).get("access_level"),
                    "filename": (h.payload or {}).get("filename"),
                }
                for h in hits
            ],
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

