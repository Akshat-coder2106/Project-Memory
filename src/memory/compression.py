"""Memory compression - summarize old memories when count exceeds threshold."""

from pathlib import Path
from typing import Optional

from memory.long_term import (
    get_memory_count,
    get_oldest_memories,
    replace_with_compressed,
)
from memory.embeddings import encode
from llm.openrouter import summarize_memories
from config import MEMORY_COMPRESSION_THRESHOLD


def maybe_compress(
    threshold: int = MEMORY_COMPRESSION_THRESHOLD,
    compress_count: int = 15,
    db_path: Optional[Path] = None,
    user_id: Optional[int] = None,
    thread_id: Optional[int] = None,
) -> bool:
    """
    If memory count > threshold, compress oldest memories into a summary.
    Uses a single atomic transaction so we never delete without storing the summary (no data loss).
    """
    count = get_memory_count(db_path=db_path, user_id=user_id, thread_id=thread_id)
    if count < threshold:
        return False

    oldest = get_oldest_memories(
        compress_count,
        db_path=db_path,
        user_id=user_id,
        thread_id=thread_id,
    )
    if not oldest:
        return False

    texts = [m.content for m in oldest]
    summary = summarize_memories(texts)
    if not summary:
        return False

    content = f"[Compressed summary] {summary}"
    try:
        embedding = encode(content)
    except Exception:
        embedding = None

    return replace_with_compressed(
        old_memories=oldest,
        new_content=content,
        new_embedding=embedding,
        db_path=db_path,
        user_id=user_id,
        thread_id=thread_id,
    )
