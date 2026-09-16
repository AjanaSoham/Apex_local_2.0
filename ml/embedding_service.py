"""Embedding provider with an offline, deterministic fallback."""

import hashlib
import math
import os
import re

MODEL_NAME = "all-MiniLM-L6-v2"
FALLBACK_MODEL_NAME = "hashing-tfidf-384-v1"
_model = None


def _load_model():
    """Load the optional transformer lazily so the service can start offline."""
    global _model
    if _model is not None:
        return _model
    if os.getenv("ENABLE_SENTENCE_TRANSFORMER", "").lower() not in {"1", "true", "yes"}:
        return None
    try:
        from sentence_transformers import SentenceTransformer
        _model = SentenceTransformer(MODEL_NAME)
    except Exception:
        _model = None
    return _model


def generate_embedding(text: str) -> list:
    """
    Convert text into a numerical embedding.
    """

    model = _load_model()
    if model is not None:
        return model.encode(text, convert_to_numpy=True).tolist()

    vector = [0.0] * 384
    for token in re.findall(r"[a-z0-9+#.]{2,}", text.lower()):
        digest = hashlib.sha256(token.encode("utf-8")).digest()
        index = int.from_bytes(digest[:2], "big") % len(vector)
        vector[index] += 1.0 if digest[2] % 2 else -1.0
    magnitude = math.sqrt(sum(value * value for value in vector))
    return [value / magnitude for value in vector] if magnitude else vector


def active_model_name() -> str:
    return MODEL_NAME if _load_model() is not None else FALLBACK_MODEL_NAME
