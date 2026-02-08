"""
Sentence embeddings with VL-JEPA latent space.

VL-JEPA (Joint Embedding Predictive Architecture) operates in embedding space rather than
token space. When USE_VLJEPA=1 and on Mac with MLX, uses VL-JEPA's Y_Encoder for
self-supervised representation learning. Otherwise uses sentence-transformers.
"""

import os
from typing import Optional

# Lazy load to avoid importing heavy deps at startup
_model = None
_model_name = "sentence-transformers/all-MiniLM-L6-v2"


def _use_vljepa() -> bool:
    """Check if VL-JEPA backend should be used."""
    if os.environ.get("USE_VLJEPA", "0").lower() not in ("1", "true", "yes"):
        return False
    try:
        from memory.vljepa_backend import is_available
        return is_available()
    except Exception:
        return False


def _get_model():
    """Lazy-load the sentence-transformers model (fallback backend)."""
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer
        _model = SentenceTransformer(_model_name)
    return _model


def encode(text: str | list[str]) -> list[float] | list[list[float]]:
    """
    Encode text into the latent embedding space.
    Uses VL-JEPA when USE_VLJEPA=1 (Mac + MLX); else sentence-transformers.
    Single string -> single embedding; list -> list of embeddings.
    """
    if _use_vljepa():
        try:
            from memory.vljepa_backend import encode_vljepa
            return encode_vljepa(text)
        except Exception:
            pass  # Fall through to sentence-transformers
    model = _get_model()
    is_single = isinstance(text, str)
    if is_single:
        text = [text]
    emb = model.encode(text, convert_to_numpy=True)
    if is_single:
        return emb[0].tolist()
    return [e.tolist() for e in emb]


def get_backend() -> str:
    """Return current embedding backend name."""
    return "vljepa" if _use_vljepa() else "sentence-transformers"


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """Cosine similarity between two vectors."""
    import numpy as np
    va = np.array(a, dtype=float)
    vb = np.array(b, dtype=float)
    dot = np.dot(va, vb)
    norm_a = np.linalg.norm(va)
    norm_b = np.linalg.norm(vb)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return float(dot / (norm_a * norm_b))


def jepa_inspired_refine(
    query_embedding: list[float],
    memory_embeddings: list[list[float]],
    alpha: float = 0.1,
) -> list[float]:
    """
    VL-JEPA-inspired refinement: nudge query embedding toward the centroid of
    memory embeddings for better alignment in latent space.
    """
    import numpy as np
    if not memory_embeddings:
        return query_embedding
    centroid = np.mean(memory_embeddings, axis=0)
    q = np.array(query_embedding)
    refined = q + alpha * (centroid - q)
    return refined.tolist()
