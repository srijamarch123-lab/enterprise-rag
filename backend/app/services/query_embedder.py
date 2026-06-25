from __future__ import annotations

from typing import Optional

from fastembed import TextEmbedding


MODEL_NAME = "BAAI/bge-small-en-v1.5"
_embedder: Optional[TextEmbedding] = None


def get_embedder() -> TextEmbedding:
    global _embedder
    if _embedder is None:
        # Must match embedder.py model used during ingestion
        _embedder = TextEmbedding(MODEL_NAME)
    return _embedder


def embed_query(query: str) -> list[float]:
    embedder = get_embedder()
    vectors = list(embedder.embed([query]))
    if not vectors:
        return []
    return vectors[0].tolist()

