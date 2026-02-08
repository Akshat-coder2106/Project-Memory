"""
VL-JEPA backend for text embeddings.

Uses the Y_Encoder from VL-JEPA (Joint Embedding Predictive Architecture) to encode
text into a semantic latent space. VL-JEPA predicts embeddings in abstract representation
space rather than token space, focusing on task-relevant semantics.

Requires: Mac (Apple Silicon) with MLX, vljepa package.
Fallback: Use sentence-transformers when VL-JEPA unavailable.
"""

import os
from typing import Optional

_vljepa_model = None
_vljepa_processor = None


def is_available() -> bool:
    """Check if VL-JEPA can be used (Mac + MLX + vljepa installed)."""
    if os.environ.get("USE_VLJEPA", "0").lower() not in ("1", "true", "yes"):
        return False
    try:
        import mlx.core as mx  # noqa: F401
        import platform
        if platform.system() != "Darwin":
            return False
    except ImportError:
        return False
    try:
        _load_vljepa()
        return _vljepa_model is not None
    except Exception:
        return False


def _load_vljepa():
    """Lazy-load VL-JEPA model and processor."""
    global _vljepa_model, _vljepa_processor
    if _vljepa_model is not None:
        return
    try:
        from vljepa.main import VLJEPA
        from transformers import AutoProcessor
        import mlx.core as mx

        model_id = os.environ.get("VLJEPA_MODEL_ID", "google/paligemma-3b-mix-224")
        _vljepa_model = VLJEPA(model_id)
        mx.eval(_vljepa_model.parameters())
        _vljepa_processor = AutoProcessor.from_pretrained(model_id)
    except Exception as e:
        raise RuntimeError(f"VL-JEPA load failed: {e}") from e


def encode_vljepa(text: str | list[str]) -> list[float] | list[list[float]]:
    """
    Encode text using VL-JEPA Y_Encoder (text encoder).
    Returns embeddings in VL-JEPA latent space.
    """
    _load_vljepa()
    import mlx.core as mx
    import numpy as np

    is_single = isinstance(text, str)
    if is_single:
        text = [text]

    # Tokenize
    tokens = _vljepa_processor.tokenizer(
        text,
        return_tensors="np",
        padding=True,
        truncation=True,
        max_length=512,
    ).input_ids

    # Encode via Y_Encoder (text → embedding)
    token_ids = mx.array(tokens)
    embeddings = _vljepa_model.y_encoder(token_ids)

    # MLX → numpy → list
    emb_np = np.array(embeddings)
    if is_single:
        return emb_np[0].tolist()
    return [e.tolist() for e in emb_np]
