import re
from typing import Iterable


def normalize_query(query: str) -> str:
    """Normalize a user query.

    - lowercase
    - keep only a-z0-9 and spaces
    - collapse whitespace
    - drop stopwords when nltk is available

    If nltk stopwords are unavailable (not installed / not downloaded),
    it falls back to returning tokens without stopword removal.
    """

    if query is None:
        return ""

    # Lowercase
    query = query.lower().strip()

    # Normalize punctuation/special chars: replace with spaces, keep [a-z0-9 ]
    query = re.sub(r"[^a-z0-9\s]", " ", query)

    # Collapse whitespace
    query = re.sub(r"\s+", " ", query).strip()
    if not query:
        return ""

    tokens: list[str] = query.split()

    # Optional stopword removal
    try:
        import nltk  # type: ignore
        from nltk.corpus import stopwords  # type: ignore

        # If resources aren't downloaded, nltk may raise LookupError
        try:
            stop_words = set(stopwords.words("english"))
        except LookupError:
            # stopwords missing
            stop_words = set()

        if stop_words:
            tokens = [t for t in tokens if t not in stop_words]
    except Exception:
        # NLTK not installed or any runtime issue: skip stopword removal
        pass

    return " ".join(tokens)

