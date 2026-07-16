from __future__ import annotations

import threading
import time
from typing import Optional

from fastembed import TextEmbedding

MODEL_NAME = "BAAI/bge-small-en-v1.5"
_embedder: Optional[TextEmbedding] = None
_lock = threading.Lock()

# Query embedding cache
CACHE_TTL_SECONDS = 300


def get_embedder() -> TextEmbedding:
    global _embedder
    if _embedder is None:
        with _lock:
            if _embedder is None:
                import os
                cache_dir = os.environ.get("FASTEMBED_CACHE_PATH") or "./fastembed_cache"
                os.makedirs(cache_dir, exist_ok=True)
                _embedder = TextEmbedding(MODEL_NAME, cache_dir=cache_dir)
    return _embedder


def embed_query(query: str) -> list[float]:
    if not query or not isinstance(query, str) or not query.strip():
        return []

    query_key = query.lower().strip()
    cache_key = f"query_embed:{query_key}"

    from app.services.redis_service import get_redis_client
    import json

    redis_client = get_redis_client()
    try:
        cached = redis_client.get(cache_key)
        if cached:
            return json.loads(cached)
    except Exception:
        pass

    embedder = get_embedder()
    vectors = list(embedder.embed([query]))
    if not vectors:
        return []
    result = vectors[0].tolist()

    try:
        redis_client.set(cache_key, json.dumps(result), ex=CACHE_TTL_SECONDS)
    except Exception:
        pass

    return result

