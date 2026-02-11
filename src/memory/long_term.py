"""Long-term semantic memory - SQLite storage with categories."""

import os
import sqlite3
import json
import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

# Resolve DB path relative to project root
PROJECT_ROOT = Path(__file__).parent.parent.parent
_db_env_path = (os.environ.get("MEMORY_DB_PATH") or "").strip()
_running_on_render = bool(
    (os.environ.get("RENDER") or "").strip()
    or (os.environ.get("RENDER_SERVICE_ID") or "").strip()
    or (os.environ.get("RENDER_SERVICE_NAME") or "").strip()
)
if _db_env_path:
    DEFAULT_DB_PATH = Path(_db_env_path).expanduser()
elif _running_on_render:
    # Render persistent disks are mounted at /var/data.
    DEFAULT_DB_PATH = Path("/var/data/memories.db")
else:
    DEFAULT_DB_PATH = PROJECT_ROOT / "data" / "memories.db"

LEGACY_DB_PATH = PROJECT_ROOT / "data" / "memories.db"


def _maybe_migrate_legacy_db(target_path: Path) -> None:
    """
    One-time safety migration:
    if runtime path changed (e.g. to /var/data on Render) and target DB
    doesn't exist yet, copy the legacy DB so users do not need to sign up again.
    """
    try:
        if target_path == LEGACY_DB_PATH:
            return
        if target_path.exists():
            return
        if not LEGACY_DB_PATH.exists():
            return
        target_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(str(LEGACY_DB_PATH), str(target_path))
    except Exception:
        # Non-fatal: app can still start with a fresh DB.
        pass


@dataclass
class Memory:
    """A single long-term memory with embedding."""
    id: Optional[int]
    user_id: Optional[int]
    thread_id: Optional[int]
    content: str
    category: str
    embedding: Optional[list[float]]
    created_at: datetime

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "thread_id": self.thread_id,
            "content": self.content,
            "category": self.category,
            "embedding": self.embedding,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


def _get_connection(db_path: Path = None) -> sqlite3.Connection:
    """Get DB connection, creating data dir and table if needed."""
    path = db_path or DEFAULT_DB_PATH
    _maybe_migrate_legacy_db(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    return conn


def _column_exists(conn: sqlite3.Connection, table: str, column: str) -> bool:
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return any(r["name"] == column for r in rows)


def init_db(db_path: Path = None) -> None:
    """Create/migrate users, messages, and memories tables."""
    conn = _get_connection(db_path)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            thread_id INTEGER,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS memories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            thread_id INTEGER,
            content TEXT NOT NULL,
            category TEXT NOT NULL,
            embedding_blob BLOB,
            created_at TEXT NOT NULL,
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS chat_threads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            device_id TEXT NOT NULL DEFAULT 'default',
            title TEXT NOT NULL,
            is_temporary INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
    """)
    # Migration for older databases created before user_id existed.
    if not _column_exists(conn, "memories", "user_id"):
        conn.execute("ALTER TABLE memories ADD COLUMN user_id INTEGER")
    if not _column_exists(conn, "memories", "thread_id"):
        conn.execute("ALTER TABLE memories ADD COLUMN thread_id INTEGER")
    if not _column_exists(conn, "messages", "thread_id"):
        conn.execute("ALTER TABLE messages ADD COLUMN thread_id INTEGER")
    if not _column_exists(conn, "chat_threads", "is_temporary"):
        conn.execute("ALTER TABLE chat_threads ADD COLUMN is_temporary INTEGER NOT NULL DEFAULT 0")
    if not _column_exists(conn, "chat_threads", "device_id"):
        conn.execute("ALTER TABLE chat_threads ADD COLUMN device_id TEXT NOT NULL DEFAULT 'default'")
    conn.execute("UPDATE chat_threads SET device_id = 'default' WHERE device_id IS NULL OR TRIM(device_id) = ''")

    conn.execute("CREATE INDEX IF NOT EXISTS idx_users_username ON users(username)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_messages_user_id ON messages(user_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_messages_created_at ON messages(created_at)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_messages_user_thread_created ON messages(user_id, thread_id, created_at)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_category ON memories(category)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_created_at ON memories(created_at)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_memories_user_id ON memories(user_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_memories_thread_id ON memories(thread_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_memories_user_category ON memories(user_id, category)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_memories_user_thread_category ON memories(user_id, thread_id, category)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_chat_threads_user_updated ON chat_threads(user_id, updated_at)")
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_chat_threads_user_device_updated ON chat_threads(user_id, device_id, updated_at)"
    )
    conn.commit()
    conn.close()


def add_memory(
    content: str,
    category: str,
    embedding: Optional[list[float]] = None,
    db_path: Path = None,
    user_id: Optional[int] = None,
    thread_id: Optional[int] = None,
) -> Memory:
    """Insert a memory and return it with id."""
    conn = _get_connection(db_path)
    now = datetime.utcnow().isoformat()
    emb_blob = json.dumps(embedding).encode() if embedding else None
    cursor = conn.execute(
        "INSERT INTO memories (user_id, thread_id, content, category, embedding_blob, created_at) VALUES (?, ?, ?, ?, ?, ?)",
        (user_id, thread_id, content, category, emb_blob, now),
    )
    conn.commit()
    row_id = cursor.lastrowid
    conn.close()
    return Memory(
        id=row_id,
        user_id=user_id,
        thread_id=thread_id,
        content=content,
        category=category,
        embedding=embedding,
        created_at=datetime.fromisoformat(now),
    )


def get_memories_by_category(
    category: str,
    db_path: Path = None,
    user_id: Optional[int] = None,
    thread_id: Optional[int] = None,
) -> list[Memory]:
    """Fetch all memories in a category."""
    conn = _get_connection(db_path)
    if user_id is None and thread_id is None:
        rows = conn.execute(
            "SELECT id, user_id, thread_id, content, category, embedding_blob, created_at FROM memories WHERE category = ? ORDER BY created_at ASC",
            (category,),
        ).fetchall()
    elif user_id is not None and thread_id is None:
        rows = conn.execute(
            "SELECT id, user_id, thread_id, content, category, embedding_blob, created_at FROM memories WHERE category = ? AND user_id = ? ORDER BY created_at ASC",
            (category, user_id),
        ).fetchall()
    elif user_id is None and thread_id is not None:
        rows = conn.execute(
            "SELECT id, user_id, thread_id, content, category, embedding_blob, created_at FROM memories WHERE category = ? AND thread_id = ? ORDER BY created_at ASC",
            (category, thread_id),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT id, user_id, thread_id, content, category, embedding_blob, created_at FROM memories WHERE category = ? AND user_id = ? AND thread_id = ? ORDER BY created_at ASC",
            (category, user_id, thread_id),
        ).fetchall()
    conn.close()
    return [_row_to_memory(r) for r in rows]


def get_all_memories(
    db_path: Path = None,
    user_id: Optional[int] = None,
    thread_id: Optional[int] = None,
) -> list[Memory]:
    """Fetch all memories ordered by creation time."""
    conn = _get_connection(db_path)
    if user_id is None and thread_id is None:
        rows = conn.execute(
            "SELECT id, user_id, thread_id, content, category, embedding_blob, created_at FROM memories ORDER BY created_at ASC"
        ).fetchall()
    elif user_id is not None and thread_id is None:
        rows = conn.execute(
            "SELECT id, user_id, thread_id, content, category, embedding_blob, created_at FROM memories WHERE user_id = ? ORDER BY created_at ASC",
            (user_id,),
        ).fetchall()
    elif user_id is None and thread_id is not None:
        rows = conn.execute(
            "SELECT id, user_id, thread_id, content, category, embedding_blob, created_at FROM memories WHERE thread_id = ? ORDER BY created_at ASC",
            (thread_id,),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT id, user_id, thread_id, content, category, embedding_blob, created_at FROM memories WHERE user_id = ? AND thread_id = ? ORDER BY created_at ASC",
            (user_id, thread_id),
        ).fetchall()
    conn.close()
    return [_row_to_memory(r) for r in rows]


def get_memory_count(
    db_path: Path = None,
    user_id: Optional[int] = None,
    thread_id: Optional[int] = None,
) -> int:
    """Return total number of memories."""
    conn = _get_connection(db_path)
    if user_id is None and thread_id is None:
        count = conn.execute("SELECT COUNT(*) FROM memories").fetchone()[0]
    elif user_id is not None and thread_id is None:
        count = conn.execute("SELECT COUNT(*) FROM memories WHERE user_id = ?", (user_id,)).fetchone()[0]
    elif user_id is None and thread_id is not None:
        count = conn.execute("SELECT COUNT(*) FROM memories WHERE thread_id = ?", (thread_id,)).fetchone()[0]
    else:
        count = conn.execute(
            "SELECT COUNT(*) FROM memories WHERE user_id = ? AND thread_id = ?",
            (user_id, thread_id),
        ).fetchone()[0]
    conn.close()
    return count


def delete_memories(
    ids: list[int],
    db_path: Path = None,
    user_id: Optional[int] = None,
    thread_id: Optional[int] = None,
) -> None:
    """Delete memories by id list."""
    if not ids:
        return
    conn = _get_connection(db_path)
    placeholders = ",".join("?" * len(ids))
    if user_id is None and thread_id is None:
        conn.execute(f"DELETE FROM memories WHERE id IN ({placeholders})", ids)
    elif user_id is not None and thread_id is None:
        conn.execute(f"DELETE FROM memories WHERE user_id = ? AND id IN ({placeholders})", [user_id] + ids)
    elif user_id is None and thread_id is not None:
        conn.execute(f"DELETE FROM memories WHERE thread_id = ? AND id IN ({placeholders})", [thread_id] + ids)
    else:
        conn.execute(
            f"DELETE FROM memories WHERE user_id = ? AND thread_id = ? AND id IN ({placeholders})",
            [user_id, thread_id] + ids,
        )
    conn.commit()
    conn.close()


def has_similar_memory(
    embedding: list[float],
    category: str,
    threshold: float,
    db_path: Path = None,
    user_id: Optional[int] = None,
    thread_id: Optional[int] = None,
) -> bool:
    """Return True if a memory in this category exists with similarity >= threshold."""
    candidates = get_memories_by_category(category, db_path=db_path, user_id=user_id, thread_id=thread_id)
    if not embedding:
        return False
    from memory.embeddings import cosine_similarity
    for m in candidates:
        if m.embedding and cosine_similarity(embedding, m.embedding) >= threshold:
            return True
    return False


def get_oldest_memories(
    limit: int,
    db_path: Path = None,
    user_id: Optional[int] = None,
    thread_id: Optional[int] = None,
) -> list[Memory]:
    """Get oldest N memories for compression."""
    conn = _get_connection(db_path)
    if user_id is None and thread_id is None:
        rows = conn.execute(
            "SELECT id, user_id, thread_id, content, category, embedding_blob, created_at FROM memories ORDER BY created_at ASC LIMIT ?",
            (limit,),
        ).fetchall()
    elif user_id is not None and thread_id is None:
        rows = conn.execute(
            "SELECT id, user_id, thread_id, content, category, embedding_blob, created_at FROM memories WHERE user_id = ? ORDER BY created_at ASC LIMIT ?",
            (user_id, limit),
        ).fetchall()
    elif user_id is None and thread_id is not None:
        rows = conn.execute(
            "SELECT id, user_id, thread_id, content, category, embedding_blob, created_at FROM memories WHERE thread_id = ? ORDER BY created_at ASC LIMIT ?",
            (thread_id, limit),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT id, user_id, thread_id, content, category, embedding_blob, created_at FROM memories WHERE user_id = ? AND thread_id = ? ORDER BY created_at ASC LIMIT ?",
            (user_id, thread_id, limit),
        ).fetchall()
    conn.close()
    return [_row_to_memory(r) for r in rows]


def replace_with_compressed(
    old_memories: list[Memory],
    new_content: str,
    new_embedding: Optional[list[float]] = None,
    db_path: Path = None,
    user_id: Optional[int] = None,
    thread_id: Optional[int] = None,
) -> bool:
    """Atomically add one summary memory and remove the old ones. Prevents data loss if one step fails."""
    if not old_memories:
        return False
    resolved_user_id = user_id if user_id is not None else old_memories[0].user_id
    resolved_thread_id = thread_id if thread_id is not None else old_memories[0].thread_id
    conn = _get_connection(db_path)
    try:
        now = datetime.utcnow().isoformat()
        emb_blob = json.dumps(new_embedding).encode() if new_embedding else None
        conn.execute(
            "INSERT INTO memories (user_id, thread_id, content, category, embedding_blob, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (resolved_user_id, resolved_thread_id, new_content, "misc", emb_blob, now),
        )
        ids = [m.id for m in old_memories if m.id is not None]
        if ids:
            placeholders = ",".join("?" * len(ids))
            if resolved_user_id is None and resolved_thread_id is None:
                conn.execute(f"DELETE FROM memories WHERE id IN ({placeholders})", ids)
            elif resolved_user_id is not None and resolved_thread_id is None:
                conn.execute(
                    f"DELETE FROM memories WHERE user_id = ? AND id IN ({placeholders})",
                    [resolved_user_id] + ids,
                )
            elif resolved_user_id is None and resolved_thread_id is not None:
                conn.execute(
                    f"DELETE FROM memories WHERE thread_id = ? AND id IN ({placeholders})",
                    [resolved_thread_id] + ids,
                )
            else:
                conn.execute(
                    f"DELETE FROM memories WHERE user_id = ? AND thread_id = ? AND id IN ({placeholders})",
                    [resolved_user_id, resolved_thread_id] + ids,
                )
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
    user_id = row["user_id"] if "user_id" in row.keys() else None
    thread_id = row["thread_id"] if "thread_id" in row.keys() else None
    return Memory(
        id=row["id"],
        user_id=user_id,
        thread_id=thread_id,
        content=row["content"],
        category=row["category"],
        embedding=embedding,
        created_at=datetime.fromisoformat(row["created_at"]),
    )
