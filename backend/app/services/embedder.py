import uuid
from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct, VectorParams, Distance
from sqlalchemy.orm import Session
from fastembed import TextEmbedding


from app.models import Chunk, Document, DocumentStatus, AccessLevel, UserRole
from app.config.settings import get_settings

settings = get_settings()

VECTOR_DIM = 384  # all-MiniLM-L6-v2 dimension
_model = None

def _get_model():
    global _model
    if _model is None:
        import os
        cache_dir = os.environ.get("FASTEMBED_CACHE_PATH") or "./fastembed_cache"
        os.makedirs(cache_dir, exist_ok=True)
        _model = TextEmbedding("BAAI/bge-small-en-v1.5", cache_dir=cache_dir)
    return _model


def _get_qdrant() -> QdrantClient:
    return QdrantClient(url=settings.qdrant_url, api_key=settings.qdrant_api_key)

def ensure_collection(client: QdrantClient):
    existing = [c.name for c in client.get_collections().collections]
    if settings.qdrant_collection_name not in existing:
        client.create_collection(
            collection_name=settings.qdrant_collection_name,
            vectors_config=VectorParams(size=VECTOR_DIM, distance=Distance.COSINE),
        )

def check_already_embedded(document_id: int, db: Session) -> bool:
    chunks = db.query(Chunk).filter(Chunk.document_id == document_id).all()
    if not chunks:
        return False
    return all(c.is_embedded for c in chunks)

def _visible_roles_for_access_level(access_level: AccessLevel) -> list[str]:
    """
    Role visibility policy:
    - public/internal -> admin, hr, manager, employee
    - confidential -> admin, hr, manager
    - restricted -> admin, hr
    """
    if access_level in (AccessLevel.public, AccessLevel.internal):
        return [str(UserRole.admin), str(UserRole.hr), str(UserRole.manager), str(UserRole.employee)]
    if access_level == AccessLevel.confidential:
        return [str(UserRole.admin), str(UserRole.hr), str(UserRole.manager)]
    if access_level == AccessLevel.restricted:
        return [str(UserRole.admin), str(UserRole.hr)]
    # fallback
    return [str(UserRole.admin), str(UserRole.hr), str(UserRole.manager), str(UserRole.employee)]


def embed_document(document: Document, db: Session) -> dict:
    """Embed a document, continuing even if some chunks fail.

    - If all chunks are already embedded => skipped.
    - Otherwise embed only chunks where is_embedded=False.
    - On per-chunk failure: record Chunk.embedding_error and keep going.
    - If at least one chunk succeeds => mark document.status=embedded.
    - If all remaining chunks fail => mark document.status=failed.
    """
    if check_already_embedded(document.id, db):
        return {"skipped": True, "reason": "already embedded"}

    qdrant_client = _get_qdrant()
    ensure_collection(qdrant_client)
    model = _get_model()

    chunks = (
        db.query(Chunk)
        .filter(Chunk.document_id == document.id, Chunk.is_embedded == False)
        .order_by(Chunk.chunk_index)
        .all()
    )

    if not chunks:
        return {"embedded": 0}

    visible_roles = _visible_roles_for_access_level(document.access_level)

    embedded_count = 0
    failed_count = 0

    # Embed chunk-by-chunk to isolate failures
    for chunk in chunks:
        try:
            vector = next(model.embed([chunk.text]))
            point_id = str(uuid.uuid4())
            point = PointStruct(
                id=point_id,
                vector=vector,
                payload={
                    "chunk_id": chunk.id,
                    "document_id": document.id,
                    "chunk_index": chunk.chunk_index,
                    "page_number": chunk.page_number,
                    "department": document.department,
                    "access_level": document.access_level,
                    "visible_roles": visible_roles,
                    "filename": document.original_filename,
                    "file_type": document.file_type,
                    "text_preview": chunk.text[:200],
                },
            )

            qdrant_client.upsert(
                collection_name=settings.qdrant_collection_name,
                points=[point],
            )

            chunk.qdrant_point_id = point_id
            chunk.is_embedded = True
            chunk.embedding_error = None
            embedded_count += 1

        except Exception as e:
            db.rollback()
            chunk.is_embedded = False
            chunk.embedding_error = str(e)
            failed_count += 1
            # persist per-chunk failure and continue
            db.add(chunk)
            db.commit()

    if embedded_count > 0 and failed_count == 0:
        document.status = DocumentStatus.embedded
    elif embedded_count > 0:
        # partially embedded; keep as embedded so UI can retrieve successes
        document.status = DocumentStatus.embedded
    else:
        document.status = DocumentStatus.failed

    db.commit()
    return {
        "embedded": embedded_count,
        "failed": failed_count,
        "remaining": len(chunks),
    }

def embed_all_documents(db: Session) -> dict:
    """Embed all documents that are chunked (or in embedding state).

    Continues after per-document errors; embeds each document independently.
    """
    docs = (
        db.query(Document)
        .filter(Document.status.in_([DocumentStatus.chunked, DocumentStatus.embedding]))
        .order_by(Document.id)
        .all()
    )

    results = {
        "processed": 0,
        "skipped": 0,
        "failed": 0,
        "errors": {},
    }

    for doc in docs:
        try:
            # attempt embedding regardless of previous embedding attempt
            doc.status = DocumentStatus.embedding
            db.commit()

            result = embed_document(doc, db)
            if result.get("skipped"):
                results["skipped"] += 1
            else:
                # If embed_document marked it failed, count as failed (but still continue)
                if doc.status == DocumentStatus.failed:
                    results["failed"] += 1
                else:
                    results["processed"] += 1

        except Exception as e:
            doc.status = DocumentStatus.failed
            db.commit()
            results["failed"] += 1
            results["errors"][doc.id] = str(e)

    return results

def reprocess_document(document_id: int, db: Session) -> dict:
    from app.services.chunker import chunk_document
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise ValueError(f"Document {document_id} not found")
    qdrant_client = _get_qdrant()
    chunks = db.query(Chunk).filter(Chunk.document_id == document_id).all()
    point_ids = [c.qdrant_point_id for c in chunks if c.qdrant_point_id]
    if point_ids:
        qdrant_client.delete(
            collection_name=settings.qdrant_collection_name,
            points_selector=point_ids,
        )
    chunk_document(doc, db)
    return embed_document(doc, db)

def get_qdrant_stats() -> dict:
    client = _get_qdrant()
    try:
        info = client.get_collection(settings.qdrant_collection_name)
        return {
            "collection": settings.qdrant_collection_name,
            "vectors_count": info.vectors_count,
            "points_count": info.points_count,
            "status": str(info.status),
        }
    except Exception as e:
        return {"error": str(e)}