"""
Sentence embeddings with VL-JEPA latent space.

VL-JEPA (Joint Embedding Predictive Architecture) operates in embedding space rather than
token space. When USE_VLJEPA=1 and on Mac with MLX, uses VL-JEPA's Y_Encoder for
self-supervised representation learning. Otherwise uses sentence-transformers.
"""

import hashlib
import math
import os
import re
from typing import Optional

# Lazy load to avoid importing heavy deps at startup
_model = None
_model_name = "sentence-transformers/all-MiniLM-L6-v2"


def _is_render() -> bool:
    """Detect Render runtime."""
    return os.environ.get("RENDER", "").strip().lower() in ("1", "true", "yes")


def _embedding_backend() -> str:
    """
    Select embedding backend.
    Priority:
    1) EMBEDDING_BACKEND env override
    2) VL-JEPA if enabled/available
    3) Lite backend on Render (reliability on low-memory instances)
    4) sentence-transformers locally
    """
    explicit = (os.environ.get("EMBEDDING_BACKEND") or "").strip().lower()
    if explicit in ("lite", "hash"):
        return "lite"
    if explicit in ("vljepa", "vl-jepa"):
        return "vljepa"
    if explicit in ("sentence-transformers", "sentence", "st"):
        return "sentence-transformers"
    if _use_vljepa():
        return "vljepa"
    if _is_render():
        return "lite"
    return "sentence-transformers"


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


def _lite_dim() -> int:
    raw = (os.environ.get("LITE_EMBEDDING_DIM") or "256").strip()
    try:
        dim = int(raw)
    except ValueError:
        dim = 256
    return max(64, min(dim, 1024))


def _tokenize(text: str) -> list[str]:
    return re.findall(r"[a-z0-9']+", (text or "").lower())


def _encode_lite_single(text: str) -> list[float]:
    """
    Lightweight deterministic hashing-based embedding.
    Good for low-memory environments where transformer models are too heavy.
    """
    dim = _lite_dim()
    vec = [0.0] * dim
    tokens = _tokenize(text)
    if not tokens:
        return vec

    for tok in tokens:
        digest = hashlib.sha256(tok.encode("utf-8")).digest()
        for i in range(4):
            idx = int.from_bytes(digest[i * 2 : i * 2 + 2], "big") % dim
            sign = 1.0 if ((digest[16 + i] & 1) == 0) else -1.0
            weight = 1.0 + (digest[20 + i] / 255.0) * 0.5
            vec[idx] += sign * weight

    norm = math.sqrt(sum(v * v for v in vec))
    if norm > 0:
        vec = [v / norm for v in vec]
    return vec


def _encode_lite(text: str | list[str]) -> list[float] | list[list[float]]:
    if isinstance(text, str):
        return _encode_lite_single(text)
    return [_encode_lite_single(t) for t in text]


def encode(text: str | list[str]) -> list[float] | list[list[float]]:
    """
    Encode text into the latent embedding space.
    Uses selected backend (vljepa/sentence-transformers/lite-hash).
    Single string -> single embedding; list -> list of embeddings.
    """
    backend = _embedding_backend()

    if backend == "vljepa":
        try:
            from memory.vljepa_backend import encode_vljepa
            return encode_vljepa(text)
        except Exception:
            return _encode_lite(text)

    if backend == "lite":
        return _encode_lite(text)

    try:
        model = _get_model()
        is_single = isinstance(text, str)
        if is_single:
            text = [text]
        emb = model.encode(text, convert_to_numpy=True)
        if is_single:
            return emb[0].tolist()
        return [e.tolist() for e in emb]
    except Exception:
        # Last-resort fallback to keep API responsive in constrained environments.
        return _encode_lite(text)


def get_backend() -> str:
    """Return current embedding backend name."""
    return _embedding_backend()


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
