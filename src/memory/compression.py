"""Memory compression - summarize old memories when count exceeds threshold."""

from pathlib import Path
from typing import Optional

from memory.long_term import (
    get_memory_count,
    get_oldest_memories,
    add_memory,
    delete_memories,
)
from memory.embeddings import encode
from llm.gemini import summarize_memories
from config import MEMORY_COMPRESSION_THRESHOLD


def maybe_compress(
    threshold: int = MEMORY_COMPRESSION_THRESHOLD,
    compress_count: int = 25,
    db_path: Optional[Path] = None,
) -> bool:
    """
    If memory count > threshold, compress oldest memories into a summary.
    Returns True if compression ran and succeeded.
    """
    count = get_memory_count(db_path)
    if count < threshold:
        return False

    oldest = get_oldest_memories(compress_count, db_path)
    if not oldest:
        return False

    texts = [m.content for m in oldest]
    summary = summarize_memories(texts)
    if not summary:
        return False

    content = f"[Compressed summary] {summary}"
    embedding = encode(content)

    add_memory(
        content=content,
        category="misc",
        embedding=embedding,
        db_path=db_path,
    )
    delete_memories([m.id for m in oldest if m.id], db_path)
    return True
