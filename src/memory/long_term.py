"""Long-term semantic memory - SQLite storage with categories."""

import sqlite3
import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

# Resolve DB path relative to project root
PROJECT_ROOT = Path(__file__).parent.parent.parent
DEFAULT_DB_PATH = PROJECT_ROOT / "data" / "memories.db"


@dataclass
class Memory:
    """A single long-term memory with embedding."""
    id: Optional[int]
    content: str
    category: str
    embedding: Optional[list[float]]
    created_at: datetime

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "content": self.content,
            "category": self.category,
            "embedding": self.embedding,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


def _get_connection(db_path: Path = None) -> sqlite3.Connection:
    """Get DB connection, creating data dir and table if needed."""
    path = db_path or DEFAULT_DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path: Path = None) -> None:
    """Create memories table if it doesn't exist."""
    conn = _get_connection(db_path)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS memories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            content TEXT NOT NULL,
            category TEXT NOT NULL,
            embedding_blob BLOB,
            created_at TEXT NOT NULL
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_category ON memories(category)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_created_at ON memories(created_at)")
    conn.commit()
    conn.close()


def add_memory(
    content: str,
    category: str,
    embedding: Optional[list[float]] = None,
    db_path: Path = None,
) -> Memory:
    """Insert a memory and return it with id."""
    conn = _get_connection(db_path)
    now = datetime.utcnow().isoformat()
    emb_blob = json.dumps(embedding).encode() if embedding else None
    cursor = conn.execute(
        "INSERT INTO memories (content, category, embedding_blob, created_at) VALUES (?, ?, ?, ?)",
        (content, category, emb_blob, now),
    )
    conn.commit()
    row_id = cursor.lastrowid
    conn.close()
    return Memory(
        id=row_id,
        content=content,
        category=category,
        embedding=embedding,
        created_at=datetime.fromisoformat(now),
    )


def get_memories_by_category(
    category: str,
    db_path: Path = None,
) -> list[Memory]:
    """Fetch all memories in a category."""
    conn = _get_connection(db_path)
    rows = conn.execute(
        "SELECT id, content, category, embedding_blob, created_at FROM memories WHERE category = ? ORDER BY created_at ASC",
        (category,),
    ).fetchall()
    conn.close()
    return [_row_to_memory(r) for r in rows]


def get_all_memories(db_path: Path = None) -> list[Memory]:
    """Fetch all memories ordered by creation time."""
    conn = _get_connection(db_path)
    rows = conn.execute(
        "SELECT id, content, category, embedding_blob, created_at FROM memories ORDER BY created_at ASC"
    ).fetchall()
    conn.close()
    return [_row_to_memory(r) for r in rows]


def get_memory_count(db_path: Path = None) -> int:
    """Return total number of memories."""
    conn = _get_connection(db_path)
    count = conn.execute("SELECT COUNT(*) FROM memories").fetchone()[0]
    conn.close()
    return count


def delete_memories(ids: list[int], db_path: Path = None) -> None:
    """Delete memories by id list."""
    if not ids:
        return
    conn = _get_connection(db_path)
    placeholders = ",".join("?" * len(ids))
    conn.execute(f"DELETE FROM memories WHERE id IN ({placeholders})", ids)
    conn.commit()
    conn.close()


def has_similar_memory(
    embedding: list[float],
    category: str,
    threshold: float,
    db_path: Path = None,
) -> bool:
    """Return True if a memory in this category exists with similarity >= threshold."""
    candidates = get_memories_by_category(category, db_path)
    if not embedding:
        return False
    from memory.embeddings import cosine_similarity
    for m in candidates:
        if m.embedding and cosine_similarity(embedding, m.embedding) >= threshold:
            return True
    return False


def get_oldest_memories(limit: int, db_path: Path = None) -> list[Memory]:
    """Get oldest N memories for compression."""
    conn = _get_connection(db_path)
    rows = conn.execute(
        "SELECT id, content, category, embedding_blob, created_at FROM memories ORDER BY created_at ASC LIMIT ?",
        (limit,),
    ).fetchall()
    conn.close()
    return [_row_to_memory(r) for r in rows]


def replace_with_compressed(
    old_memories: list[Memory],
    new_content: str,
    new_embedding: Optional[list[float]] = None,
    db_path: Path = None,
) -> bool:
    """Atomically add one summary memory and remove the old ones. Prevents data loss if one step fails."""
    if not old_memories:
        return False
    conn = _get_connection(db_path)
    try:
        now = datetime.utcnow().isoformat()
        emb_blob = json.dumps(new_embedding).encode() if new_embedding else None
        conn.execute(
            "INSERT INTO memories (content, category, embedding_blob, created_at) VALUES (?, ?, ?, ?)",
            (new_content, "misc", emb_blob, now),
        )
        ids = [m.id for m in old_memories if m.id is not None]
        if ids:
            placeholders = ",".join("?" * len(ids))
            conn.execute(f"DELETE FROM memories WHERE id IN ({placeholders})", ids)
        conn.commit()
        return True
    except Exception:
        conn.rollback()
        return False
    finally:
        conn.close()


def _row_to_memory(row: sqlite3.Row) -> Memory:
    emb_blob = row["embedding_blob"]
    embedding = json.loads(emb_blob.decode()) if emb_blob else None
    return Memory(
        id=row["id"],
        content=row["content"],
        category=row["category"],
        embedding=embedding,
        created_at=datetime.fromisoformat(row["created_at"]),
    )
