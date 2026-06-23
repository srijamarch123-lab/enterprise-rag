from typing import Optional, Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchValue, MatchAny

from app.database import get_db
from app.models import User, UserRole
from app.services.auth import get_current_user
from app.services.embedder import _get_qdrant, _get_model
from app.config.settings import get_settings

settings = get_settings()

router = APIRouter(prefix="/api", tags=["search"])


class SearchRequest(BaseModel):
    query: str
    limit: int = 5
    department: Optional[str] = None


def _role_policy_visible_roles(role: UserRole) -> list[str]:
    # Must match the policy used in embedder.py
    if role in (UserRole.admin, UserRole.hr, UserRole.manager, UserRole.employee):
        # admin/hr/manager/employee can always see at least "internal"
        # mapping happens in embedder from access_level -> visible_roles
        pass

    if role == UserRole.employee:
        # employee can see public/internal only
        return ["public", "internal"]
    if role == UserRole.manager:
        return ["public", "internal", "confidential"]
    if role == UserRole.hr:
        return ["public", "internal", "confidential"]
    if role == UserRole.admin:
        return ["public", "internal", "confidential", "restricted"]
    return ["public", "internal"]


def _make_query_filter(user: User, department: Optional[str]) -> Filter:
    """
    Qdrant filter based on payload stored on points.
    We filter by:
    - visible_roles contains the current user's role (string)
    - department matches when provided
    """
    # visible_roles is stored as an array in each point payload
    role_str = str(user.role)

    visible_roles_condition = FieldCondition(
        key="visible_roles",
        match=MatchAny(any=[role_str]),
    )

    must_conditions: list[FieldCondition] = [visible_roles_condition]

    if department:
        must_conditions.append(
            FieldCondition(
                key="department",
                match=MatchValue(value=department),
            )
        )

    return Filter(must=must_conditions)


def _embed_query(qdrant_model: Any, query: str) -> list[float]:
    vectors = list(qdrant_model.embed([query]))
    # fastembed returns Iterable[List[float]]; vectors[0] should be the vector
    if not vectors:
        raise HTTPException(400, "Empty query vector")
    return vectors[0]


@router.post("/search")
def search(req: SearchRequest, current_user: User = Depends(get_current_user), db=Depends(get_db)):
    try:
        if req.limit < 1 or req.limit > 50:
            raise HTTPException(400, "limit must be between 1 and 50")

        client: QdrantClient = _get_qdrant()
        collection_name = settings.qdrant_collection_name

        qdrant_model = _get_model()
        query_vector = _embed_query(qdrant_model, req.query)

        query_filter = _make_query_filter(current_user, req.department)

        hits = client.search(
            collection_name=collection_name,
            query_vector=query_vector,
            query_filter=query_filter,
            limit=req.limit,
            with_payload=True,
        )

        results = []
        for h in hits:
            payload = h.payload or {}
            results.append(
                {
                    "score": h.score,
                    "qdrant_point_id": h.id,
                    "chunk_id": payload.get("chunk_id"),
                    "document_id": payload.get("document_id"),
                    "chunk_index": payload.get("chunk_index"),
                    "page_number": payload.get("page_number"),
                    "text_preview": payload.get("text_preview"),
                }
            )
        return {"results": results}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, str(e))
