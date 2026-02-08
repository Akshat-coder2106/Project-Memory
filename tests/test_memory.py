"""Basic tests for memory components."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

# Use in-memory SQLite for tests
import os
os.environ["MEMORY_TEST"] = "1"


def test_short_term():
    from memory.short_term import ShortTermBuffer

    buf = ShortTermBuffer(max_size=3)
    buf.add("user", "hi")
    buf.add("assistant", "hello")
    buf.add("user", "bye")
    assert len(buf.messages) == 3
    buf.add("user", "overflow")
    assert len(buf.messages) == 3
    assert "overflow" in buf.format_for_context()
    print("short_term: OK")


def test_extractor():
    from memory.extractor import extract_local

    facts = extract_local("I like pizza and I'm going to Tokyo")
    assert len(facts) >= 1
    categories = {f["category"] for f in facts}
    assert "food" in categories or "travel" in categories
    print("extractor: OK")


def test_long_term(tmp_db=None):
    try:
        from sentence_transformers import SentenceTransformer  # noqa: F401
    except ImportError:
        print("long_term: SKIP (sentence-transformers not installed)")
        return
    from memory.long_term import init_db, add_memory, get_all_memories, get_memory_count, has_similar_memory
    from memory.embeddings import encode

    # Use temp path for isolated test
    import tempfile
    db_path = Path(tempfile.gettempdir()) / "test_memories.db"
    if db_path.exists():
        db_path.unlink()

    init_db(db_path)
    emb = encode("test memory content")
    m = add_memory("test memory content", "misc", emb, db_path)
    assert m.id is not None
    assert get_memory_count(db_path) == 1
    mems = get_all_memories(db_path)
    assert len(mems) == 1
    assert mems[0].content == "test memory content"

    # Deduplication
    assert has_similar_memory(emb, "misc", 0.99, db_path) is True
    assert has_similar_memory(encode("completely different"), "misc", 0.99, db_path) is False

    db_path.unlink(missing_ok=True)
    print("long_term: OK")


def test_embeddings():
    try:
        from sentence_transformers import SentenceTransformer  # noqa: F401
    except ImportError:
        print("embeddings: SKIP (sentence-transformers not installed)")
        return
    from memory.embeddings import encode, cosine_similarity

    e1 = encode("hello world")
    e2 = encode("hello there")
    assert len(e1) > 0
    sim = cosine_similarity(e1, e2)
    assert -1 <= sim <= 1
    assert cosine_similarity(e1, e1) > 0.99
    print("embeddings: OK")


def test_retrieval():
    try:
        from sentence_transformers import SentenceTransformer  # noqa: F401
    except ImportError:
        print("retrieval: SKIP (sentence-transformers not installed)")
        return
    from memory.long_term import init_db, add_memory
    from memory.embeddings import encode
    from memory.retrieval import retrieve
    import tempfile
    from pathlib import Path

    db_path = Path(tempfile.gettempdir()) / "test_retrieval.db"
    if db_path.exists():
        db_path.unlink()
    init_db(db_path)
    add_memory("likes Thai food", "food", encode("likes Thai food"), db_path)
    add_memory("allergic to peanuts", "personal", encode("allergic to peanuts"), db_path)

    mems = retrieve("What food do I like?", top_k=2, db_path=db_path)
    assert len(mems) >= 1

    db_path.unlink(missing_ok=True)
    print("retrieval: OK")


if __name__ == "__main__":
    test_short_term()
    test_extractor()
    test_embeddings()
    test_long_term()
    test_retrieval()
    print("\nAll tests passed!")
