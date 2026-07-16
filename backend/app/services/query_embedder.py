from __future__ import annotations

import time
from typing import Optional

from fastembed import TextEmbedding

MODEL_NAME = "BAAI/bge-small-en-v1.5"
_embedder: Optional[TextEmbedding] = None

# Query embedding cache
_query_cache: dict = {}
CACHE_TTL_SECONDS = 300
MAX_CACHE_SIZE = 100

def get_embedder() -> TextEmbedding:
    global _embedder
    if _embedder is None:
        import os
        cache_dir = os.environ.get("FASTEMBED_CACHE_PATH") or "./fastembed_cache"
        os.makedirs(cache_dir, exist_ok=True)
        _embedder = TextEmbedding(MODEL_NAME, cache_dir=cache_dir)
    return _embedder


def embed_query(query: str) -> list[float]:
    query_key = query.lower().strip()
    now = time.time()
    if query_key in _query_cache:
        cached_vec, cached_time = _query_cache[query_key]
        if now - cached_time < CACHE_TTL_SECONDS:
            return cached_vec
    embedder = get_embedder()
    vectors = list(embedder.embed([query]))
    if not vectors:
        return []
    result = vectors[0].tolist()
    _query_cache[query_key] = (result, now)
    if len(_query_cache) > MAX_CACHE_SIZE:
        oldest = min(_query_cache.keys(), key=lambda k: _query_cache[k][1])
        del _query_cache[oldest]
    return result
