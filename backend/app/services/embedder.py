import uuid
from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct, VectorParams, Distance
from sqlalchemy.orm import Session
from fastembed import TextEmbedding


from app.models import Chunk, Document, DocumentStatus, AccessLevel, UserRole
from app.config.settings import get_settings

settings = get_settings()

VECTOR_DIM = 384  # all-MiniLM-L6-v2 dimension
def _get_model():
    from app.services.query_embedder import get_embedder
    return get_embedder()


_qdrant_client = None

def _get_qdrant(force_reconnect: bool = False) -> QdrantClient:
    global _qdrant_client
    if _qdrant_client is None or force_reconnect:
        _qdrant_client = QdrantClient(url=settings.qdrant_url, api_key=settings.qdrant_api_key)
    return _qdrant_client

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

def _visible_roles_for_access_level(access_level: AccessLevel | str | None) -> list[str]:
    """
    Role visibility policy:
    - public/internal -> admin, hr, manager, employee
    - confidential -> admin, hr, manager
    - restricted -> admin, hr
    """
    if isinstance(access_level, str):
        try:
            access_level = AccessLevel(access_level)
        except ValueError:
            pass
    if access_level in (AccessLevel.public, AccessLevel.internal):
        return [str(UserRole.admin), str(UserRole.hr), str(UserRole.manager), str(UserRole.employee)]
    if access_level == AccessLevel.confidential:
        return [str(UserRole.admin), str(UserRole.hr), str(UserRole.manager)]
    if access_level == AccessLevel.restricted:
        return [str(UserRole.admin), str(UserRole.hr)]
    # fallback
    return [str(UserRole.admin), str(UserRole.hr), str(UserRole.manager), str(UserRole.employee)]


def embed_document(document: Document, db: Session) -> dict:
    """Embed a document using batching with chunk-by-chunk fallback.

    - If all chunks are already embedded => skipped.
    - Otherwise embed only chunks where is_embedded=False.
    - Attempt batch embedding and batch Qdrant upsert first for speed.
    - On batch failure: fall back to chunk-by-chunk execution to isolate errors.
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

    # Try batching first
    try:
        from app.services.query_embedder import safe_embed_texts
        texts = [chunk.text for chunk in chunks]
        vectors = safe_embed_texts(texts)
        
        points = []
        point_ids = []
        for chunk, vector in zip(chunks, vectors):
            point_id = str(uuid.uuid4())
            point_ids.append(point_id)
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
                    "parent_text": chunk.parent_text,
                    "owner_id": document.owner_user_id,
                    "created_at": (chunk.created_at or __import__("datetime").datetime.utcnow()).isoformat(),
                },
            )
            points.append(point)

        # Upsert all points in one batch request
        qdrant_client.upsert(
            collection_name=settings.qdrant_collection_name,
            points=points,
        )

        # Update database statuses
        for chunk, point_id in zip(chunks, point_ids):
            chunk.qdrant_point_id = point_id
            chunk.is_embedded = True
            chunk.embedding_error = None
        embedded_count = len(chunks)

    except Exception as batch_err:
        import logging
        logging.getLogger(__name__).warning("Batch embedding/upsert failed, falling back to chunk-by-chunk: %s", batch_err)
        from app.services.query_embedder import safe_embed_texts
        # Fallback to chunk-by-chunk to isolate failures
        for chunk in chunks:
            try:
                vectors = safe_embed_texts([chunk.text])
                if not vectors:
                    raise ValueError("Embedder returned empty vector")
                vector = vectors[0]
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
                        "parent_text": chunk.parent_text,
                        "owner_id": document.owner_user_id,
                        "created_at": (chunk.created_at or __import__("datetime").datetime.utcnow()).isoformat(),
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
                db.add(chunk)
                db.commit()

    if embedded_count > 0 and failed_count == 0:
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
    from app.services.extractor import extract_text
    from app.services.process_all import ensure_file_exists
    import datetime

    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise ValueError(f"Document {document_id} not found")

    doc.status = DocumentStatus.extracting
    doc.extraction_error = None
    db.commit()

    # Make sure file is present (or auto-downloaded if Drive doc)
    ensure_file_exists(doc, db)

    # Perform text extraction (OCR is executed for scanned documents)
    text, pages = extract_text(doc.file_path, doc.file_type)
    doc.extracted_text = text
    doc.page_count = pages
    doc.status = DocumentStatus.extracted
    from datetime import timezone
    doc.processed_at = datetime.datetime.now(timezone.utc).replace(tzinfo=None)
    db.commit()

    qdrant_client = _get_qdrant()
    chunks = db.query(Chunk).filter(Chunk.document_id == document_id).all()
    point_ids = [c.qdrant_point_id for c in chunks if c.qdrant_point_id]
    if point_ids:
        qdrant_client.delete(
            collection_name=settings.qdrant_collection_name,
            points_selector=point_ids,
        )

    # Perform chunking and database persistence
    chunk_document(doc, db)

    # Perform embedding generation and Qdrant upsert
    res = embed_document(doc, db)
    from app.services.redis_service import invalidate_rag_cache
    invalidate_rag_cache()
    return res

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