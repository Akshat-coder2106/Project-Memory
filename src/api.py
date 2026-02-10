"""
Backend API for the memory dashboard with per-user authentication.
"""

import os
import re
import sqlite3
import sys
import time
from datetime import datetime, timezone, timedelta
from functools import wraps
from pathlib import Path
from typing import Optional, Dict, Tuple

sys.path.insert(0, str(Path(__file__).parent))
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
except ImportError:
    pass

from flask import Flask, request, jsonify, send_from_directory, session
from werkzeug.security import generate_password_hash, check_password_hash

from memory.short_term import ShortTermBuffer
from memory.long_term import (
    init_db,
    add_memory,
    get_all_memories,
    get_memory_count,
    DEFAULT_DB_PATH,
)
from memory.extractor import extract_local, extract_with_openrouter
from memory.embeddings import encode
from memory.retrieval import retrieve
from memory.compression import maybe_compress
from llm.openrouter import generate, is_available
from config import (
    MAX_SHORT_TERM_MESSAGES,
    TOP_K_MEMORIES,
    CATEGORIES,
    DUPLICATE_SIMILARITY_THRESHOLD,
)

app = Flask(__name__, static_folder=None)
app.config["SECRET_KEY"] = (
    os.environ.get("FLASK_SECRET_KEY")
    or os.environ.get("SECRET_KEY")
    or "change-me-in-env"
)
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"

# Path to dashboard (served as static files)
DASHBOARD_DIR = Path(__file__).resolve().parent.parent / "dashboard"

SYSTEM_INSTRUCTION = """You are a helpful conversational assistant with long-term memory of the user.
Use the provided "Relevant memories" to personalize your responses. Be concise and natural.
If memories conflict with what the user just said, prioritize the most recent conversation."""

# Session state: short-term buffer per authenticated thread (user_id, thread_id)
_user_buffers: dict[tuple[int, int], ShortTermBuffer] = {}
_last_api_success = None
_fallback_count = 0


_DATETIME_QUERY_RE = re.compile(
    r"(what\s+time\s+is\s+it|what'?s\s+the\s+time|current\s+time|time\s+now|time\s+right\s+now|"
    r"today'?s\s+date|date\s+today|current\s+date|"
    r"what\s+day\s+is\s+it|which\s+day\s+is\s+it|"
    r"date\s+and\s+time|current\s+date\s+and\s+time|"
    r"tomorrow\s+date|tommorow\s+date|yesterday\s+date|"
    r"\d+\s*days?\s*(after|before|from|ago|later)|"
    r"(in|after|before)\s+\d+\s*days?)",
    re.IGNORECASE,
)


def _get_fallback_message():
    has_key = os.environ.get("OPENROUTER_API_KEY")
    return (
        "I can't connect to the AI right now. Set OPENROUTER_API_KEY in .env and restart."
        if not has_key
        else "The AI service is temporarily unavailable. Please try again in a moment."
    )


def _db_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DEFAULT_DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def _utc_now_iso() -> str:
    """UTC ISO timestamp with explicit timezone suffix for correct client parsing."""
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _is_datetime_request(text: str) -> bool:
    """Heuristic for direct current date/time questions."""
    return _datetime_mode(text) != "none"


def _datetime_mode(text: str) -> str:
    """Classify query intent: time/date/both/none."""
    t = (text or "").strip().lower()
    if not t:
        return "none"
    if _DATETIME_QUERY_RE.search(t):
        if "date" in t and "time" in t:
            return "both"
        if "date" in t or "day" in t or "today" in t:
            return "date"
        return "time"
    has_time = ("time" in t) or ("clock" in t) or ("hour" in t)
    has_date = (
        ("date" in t)
        or ("today" in t)
        or ("tomorrow" in t)
        or ("tommorow" in t)
        or ("yesterday" in t)
        or ("month" in t)
        or ("year" in t)
        or ("what day is it" in t)
        or ("which day is it" in t)
        or bool(re.search(r"\b(in|after|before)\s+\d+\s*days?\b", t))
        or bool(re.search(r"\b\d+\s*days?\s*(after|before|from|ago|later)\b", t))
    )
    if has_time and has_date:
        return "both"
    if has_time:
        return "time"
    if has_date:
        return "date"
    return "none"


def _relative_day_offset(text: str) -> int:
    """Parse relative day intent from text (e.g., tomorrow/yesterday)."""
    t = (text or "").strip().lower()
    if not t:
        return 0
    if re.search(r"\b(day\s+after\s+tomorrow|after\s+tomorrow)\b", t):
        return 2
    if re.search(r"\b(day\s+before\s+yesterday|before\s+yesterday)\b", t):
        return -2
    if re.search(r"\b(tomorrow|tommorow|tmrw|tmr)\b", t):
        return 1
    if re.search(r"\byesterday\b", t):
        return -1
    m = re.search(r"\bin\s+(\d+)\s+days?\b", t)
    if m:
        return int(m.group(1))
    m = re.search(r"\b(\d+)\s+days?\s+(after|from|later)\b", t)
    if m:
        return int(m.group(1))
    m = re.search(r"\bafter\s+(\d+)\s+days?\b", t)
    if m:
        return int(m.group(1))
    m = re.search(r"\b(\d+)\s+days?\s+(before|ago|prior)\b", t)
    if m:
        return -int(m.group(1))
    m = re.search(r"\bbefore\s+(\d+)\s+days?\b", t)
    if m:
        return -int(m.group(1))
    return 0


def _days_phrase(n: int) -> str:
    return "1 day" if n == 1 else f"{n} days"


def _current_datetime_reply(user_message: str) -> str:
    """Return concise current date/time based on what user asked."""
    now = datetime.now().astimezone()
    mode = _datetime_mode(user_message)
    offset = _relative_day_offset(user_message)
    target = now + timedelta(days=offset)
    time_part = target.strftime("%I:%M %p").lstrip("0")
    tz_part = target.strftime("%Z")
    date_part = target.strftime("%A, %B %d, %Y")
    if mode == "time":
        if offset == 0:
            return f"It is {time_part} {tz_part}."
        if offset > 0:
            return f"In {_days_phrase(offset)}, it will be around {time_part} {tz_part}."
        return f"{_days_phrase(abs(offset))} ago, it was around {time_part} {tz_part}."
    if mode == "date":
        if offset == 0:
            return f"Today is {date_part}."
        if offset == 1:
            return f"Tomorrow is {date_part}."
        if offset == 2:
            return f"Day after tomorrow is {date_part}."
        if offset == -1:
            return f"Yesterday was {date_part}."
        if offset == -2:
            return f"Day before yesterday was {date_part}."
        if offset > 0:
            return f"In {_days_phrase(offset)}, it will be {date_part}."
        return f"{_days_phrase(abs(offset))} ago, it was {date_part}."
    if offset == 0:
        return f"It is {time_part} {tz_part} on {date_part}."
    if offset > 0:
        return f"In {_days_phrase(offset)}, it will be {time_part} {tz_part} on {date_part}."
    return f"{_days_phrase(abs(offset))} ago, it was {time_part} {tz_part} on {date_part}."


def _validate_auth_payload(data: dict) -> Tuple[str, str, Optional[str]]:
    username = (data.get("username") or "").strip()
    password = (data.get("password") or "").strip()
    if len(username) < 3:
        return "", "", "Username must be at least 3 characters."
    if len(username) > 40:
        return "", "", "Username must be at most 40 characters."
    if not re.fullmatch(r"[A-Za-z0-9_.-]+", username):
        return "", "", "Username can only use letters, numbers, dot, underscore, or hyphen."
    if len(password) < 6:
        return "", "", "Password must be at least 6 characters."
    return username, password, None


def _find_user_by_username(username: str):
    conn = _db_conn()
    row = conn.execute(
        "SELECT id, username, password_hash FROM users WHERE username = ?",
        (username,),
    ).fetchone()
    conn.close()
    return row


def _create_user(username: str, password: str) -> Tuple[Optional[int], Optional[str]]:
    conn = _db_conn()
    try:
        cursor = conn.execute(
            "INSERT INTO users (username, password_hash, created_at) VALUES (?, ?, ?)",
            (username, generate_password_hash(password), _utc_now_iso()),
        )
        conn.commit()
        return cursor.lastrowid, None
    except sqlite3.IntegrityError:
        return None, "Username already exists."
    finally:
        conn.close()


def _set_session_user(user_id: int, username: str):
    session["user_id"] = user_id
    session["username"] = username


def _current_user() -> Optional[Dict]:
    uid = session.get("user_id")
    uname = session.get("username")
    if uid and uname:
        return {"id": uid, "username": uname}
    return None


def _sanitize_thread_title(title: str) -> str:
    text = re.sub(r"\s+", " ", (title or "").strip())
    if not text:
        return "New chat"
    return text[:80]


def _title_from_first_message(message: str) -> str:
    text = re.sub(r"\s+", " ", (message or "").strip())
    if not text:
        return "New chat"
    if len(text) <= 54:
        return text
    return text[:51].rstrip() + "..."


def _row_to_thread_payload(row: sqlite3.Row) -> dict:
    return {
        "id": row["id"],
        "title": row["title"],
        "is_temporary": bool(row["is_temporary"]),
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        "last_message": row["last_message"] or "",
        "last_message_at": row["last_message_at"] or row["updated_at"],
        "message_count": int(row["message_count"] or 0),
    }


def _get_thread(user_id: int, thread_id: int) -> Optional[dict]:
    conn = _db_conn()
    row = conn.execute(
        """
        SELECT
            t.id,
            t.title,
            t.is_temporary,
            t.created_at,
            t.updated_at,
            COALESCE((
                SELECT m.content
                FROM messages m
                WHERE m.user_id = t.user_id AND m.thread_id = t.id
                ORDER BY m.id DESC
                LIMIT 1
            ), '') AS last_message,
            COALESCE((
                SELECT m.created_at
                FROM messages m
                WHERE m.user_id = t.user_id AND m.thread_id = t.id
                ORDER BY m.id DESC
                LIMIT 1
            ), t.updated_at) AS last_message_at,
            (
                SELECT COUNT(*)
                FROM messages m
                WHERE m.user_id = t.user_id AND m.thread_id = t.id
            ) AS message_count
        FROM chat_threads t
        WHERE t.user_id = ? AND t.id = ?
        """,
        (user_id, thread_id),
    ).fetchone()
    conn.close()
    return _row_to_thread_payload(row) if row else None


def _list_threads(user_id: int) -> list[dict]:
    conn = _db_conn()
    rows = conn.execute(
        """
        SELECT
            t.id,
            t.title,
            t.is_temporary,
            t.created_at,
            t.updated_at,
            COALESCE((
                SELECT m.content
                FROM messages m
                WHERE m.user_id = t.user_id AND m.thread_id = t.id
                ORDER BY m.id DESC
                LIMIT 1
            ), '') AS last_message,
            COALESCE((
                SELECT m.created_at
                FROM messages m
                WHERE m.user_id = t.user_id AND m.thread_id = t.id
                ORDER BY m.id DESC
                LIMIT 1
            ), t.updated_at) AS last_message_at,
            (
                SELECT COUNT(*)
                FROM messages m
                WHERE m.user_id = t.user_id AND m.thread_id = t.id
            ) AS message_count
        FROM chat_threads t
        WHERE t.user_id = ?
        ORDER BY t.updated_at DESC, t.id DESC
        """,
        (user_id,),
    ).fetchall()
    conn.close()
    return [_row_to_thread_payload(r) for r in rows]


def _backfill_legacy_rows(user_id: int, default_thread_id: int):
    conn = _db_conn()
    conn.execute(
        "UPDATE messages SET thread_id = ? WHERE user_id = ? AND thread_id IS NULL",
        (default_thread_id, user_id),
    )
    conn.execute(
        "UPDATE memories SET thread_id = ? WHERE user_id = ? AND thread_id IS NULL",
        (default_thread_id, user_id),
    )
    conn.commit()
    conn.close()


def _create_thread(user_id: int, title: str = "New chat", is_temporary: bool = False) -> dict:
    now = _utc_now_iso()
    conn = _db_conn()
    cursor = conn.execute(
        """
        INSERT INTO chat_threads (user_id, title, is_temporary, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (user_id, _sanitize_thread_title(title), 1 if is_temporary else 0, now, now),
    )
    thread_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return _get_thread(user_id, thread_id)


def _ensure_default_thread(user_id: int) -> int:
    conn = _db_conn()
    row = conn.execute(
        "SELECT id FROM chat_threads WHERE user_id = ? ORDER BY id ASC LIMIT 1",
        (user_id,),
    ).fetchone()
    if row:
        thread_id = int(row["id"])
    else:
        now = _utc_now_iso()
        cursor = conn.execute(
            """
            INSERT INTO chat_threads (user_id, title, is_temporary, created_at, updated_at)
            VALUES (?, ?, 0, ?, ?)
            """,
            (user_id, "New chat", now, now),
        )
        thread_id = int(cursor.lastrowid)
        conn.commit()
    conn.close()
    _backfill_legacy_rows(user_id, thread_id)
    return thread_id


def _touch_thread(
    user_id: int,
    thread_id: int,
    first_user_message: Optional[str] = None,
):
    now = _utc_now_iso()
    conn = _db_conn()
    if first_user_message:
        title_hint = _title_from_first_message(first_user_message)
        conn.execute(
            """
            UPDATE chat_threads
            SET
                title = CASE
                    WHEN title = 'New chat' THEN ?
                    ELSE title
                END,
                updated_at = ?
            WHERE user_id = ? AND id = ?
            """,
            (title_hint, now, user_id, thread_id),
        )
    else:
        conn.execute(
            "UPDATE chat_threads SET updated_at = ? WHERE user_id = ? AND id = ?",
            (now, user_id, thread_id),
        )
    conn.commit()
    conn.close()


def _delete_thread(user_id: int, thread_id: int) -> Optional[int]:
    conn = _db_conn()
    row = conn.execute(
        "SELECT id FROM chat_threads WHERE user_id = ? AND id = ?",
        (user_id, thread_id),
    ).fetchone()
    if not row:
        conn.close()
        return None
    conn.execute("DELETE FROM messages WHERE user_id = ? AND thread_id = ?", (user_id, thread_id))
    conn.execute("DELETE FROM memories WHERE user_id = ? AND thread_id = ?", (user_id, thread_id))
    conn.execute("DELETE FROM chat_threads WHERE user_id = ? AND id = ?", (user_id, thread_id))
    conn.commit()
    next_row = conn.execute(
        "SELECT id FROM chat_threads WHERE user_id = ? ORDER BY updated_at DESC, id DESC LIMIT 1",
        (user_id,),
    ).fetchone()
    if next_row:
        next_thread_id = int(next_row["id"])
    else:
        now = _utc_now_iso()
        cursor = conn.execute(
            """
            INSERT INTO chat_threads (user_id, title, is_temporary, created_at, updated_at)
            VALUES (?, ?, 0, ?, ?)
            """,
            (user_id, "New chat", now, now),
        )
        next_thread_id = int(cursor.lastrowid)
        conn.commit()
    conn.close()
    _user_buffers.pop((user_id, thread_id), None)
    return next_thread_id


def _load_recent_messages(
    user_id: int,
    thread_id: int,
    limit: int = MAX_SHORT_TERM_MESSAGES,
) -> list[tuple[str, str]]:
    conn = _db_conn()
    rows = conn.execute(
        """
        SELECT role, content
        FROM messages
        WHERE user_id = ? AND thread_id = ?
        ORDER BY id DESC
        LIMIT ?
        """,
        (user_id, thread_id, limit),
    ).fetchall()
    conn.close()
    rows = list(reversed(rows))
    return [(r["role"], r["content"]) for r in rows]


def _store_message(user_id: int, thread_id: int, role: str, content: str):
    conn = _db_conn()
    conn.execute(
        """
        INSERT INTO messages (user_id, thread_id, role, content, created_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (user_id, thread_id, role, content, _utc_now_iso()),
    )
    conn.commit()
    conn.close()


def _get_messages(user_id: int, thread_id: int, limit: int = 500) -> list[dict]:
    conn = _db_conn()
    rows = conn.execute(
        """
        SELECT role, content, created_at
        FROM messages
        WHERE user_id = ? AND thread_id = ?
        ORDER BY id DESC
        LIMIT ?
        """,
        (user_id, thread_id, limit),
    ).fetchall()
    conn.close()
    rows = list(reversed(rows))
    return [
        {
            "role": r["role"],
            "content": r["content"],
            "created_at": r["created_at"],
        }
        for r in rows
    ]


def _get_user_buffer(user_id: int, thread_id: int, is_temporary: bool = False) -> ShortTermBuffer:
    key = (user_id, thread_id)
    if key in _user_buffers:
        return _user_buffers[key]
    buf = ShortTermBuffer(max_size=MAX_SHORT_TERM_MESSAGES)
    if not is_temporary:
        for role, content in _load_recent_messages(user_id, thread_id):
            buf.add(role, content)
    _user_buffers[key] = buf
    return buf


def _unauthorized():
    return jsonify({"error": "Authentication required"}), 401


def _login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        user = _current_user()
        if not user:
            return _unauthorized()
        return fn(user, *args, **kwargs)
    return wrapper


def _resolve_thread(user_id: int, raw_thread_id) -> Tuple[Optional[dict], Optional[Tuple[dict, int]]]:
    if raw_thread_id in (None, ""):
        thread_id = _ensure_default_thread(user_id)
    else:
        try:
            thread_id = int(raw_thread_id)
        except (TypeError, ValueError):
            return None, ({"error": "Invalid thread_id."}, 400)
    thread = _get_thread(user_id, thread_id)
    if not thread:
        return None, ({"error": "Thread not found."}, 404)
    return thread, None


def _process_message(
    user_id: int,
    thread_id: int,
    user_message: str,
    store_data: bool = True,
):
    global _last_api_success, _fallback_count
    from memory.long_term import has_similar_memory

    start = time.perf_counter()
    buffer = _get_user_buffer(user_id, thread_id, is_temporary=not store_data)
    is_first_message = len(buffer.messages) == 0
    buffer.add("user", user_message)
    if store_data:
        _store_message(user_id, thread_id, "user", user_message)
        _touch_thread(
            user_id,
            thread_id,
            first_user_message=user_message if is_first_message else None,
        )
    else:
        _touch_thread(user_id, thread_id)

    # Deterministic answer for current date/time queries (no model call needed).
    if _is_datetime_request(user_message):
        response = _current_datetime_reply(user_message)
        buffer.add("assistant", response)
        if store_data:
            _store_message(user_id, thread_id, "assistant", response)
        _touch_thread(user_id, thread_id)
        latency_ms = int((time.perf_counter() - start) * 1000)
        return {
            "reply": response,
            "retrieved_memories": [],
            "latency_ms": latency_ms,
            "stored_count": 0,
            "compressed": False,
            "thread_id": thread_id,
        }

    stored = []
    compressed = False
    mems = []
    if store_data:
        # Extract and store
        has_ai = is_available()
        extracted = extract_with_openrouter(user_message) if has_ai else extract_local(user_message)
        for item in extracted:
            content = item["content"]
            category = item["category"]
            try:
                embedding = encode(content)
            except Exception:
                embedding = None
            if embedding and has_similar_memory(
                embedding,
                category,
                DUPLICATE_SIMILARITY_THRESHOLD,
                user_id=user_id,
                thread_id=None,
            ):
                continue
            add_memory(
                content=content,
                category=category,
                embedding=embedding,
                user_id=user_id,
                thread_id=thread_id,
            )
            stored.append(item)

        # Compress at user scope so memory stays shared across chats for the same account.
        compressed = maybe_compress(user_id=user_id, thread_id=None)

        # Retrieve at user scope so facts learned in one chat are available in other chats.
        mems = retrieve(user_message, top_k=TOP_K_MEMORIES, user_id=user_id, thread_id=None)

    memories_text = "\n".join(f"- [{m.category}] {m.content}" for m in mems) if mems else ""
    context = f"Relevant memories:\n{memories_text}\n\nRecent conversation:\n{buffer.format_for_context()}"
    prompt = f"{context}\n\nUser: {user_message}\n\nAssistant:"

    response = generate(prompt, system_instruction=SYSTEM_INSTRUCTION)
    if response:
        _last_api_success = time.time()
    else:
        _fallback_count += 1
        response = _get_fallback_message()

    buffer.add("assistant", response)
    if store_data:
        _store_message(user_id, thread_id, "assistant", response)
    _touch_thread(user_id, thread_id)
    latency_ms = int((time.perf_counter() - start) * 1000)

    return {
        "reply": response,
        "retrieved_memories": [
            {"content": m.content, "category": m.category, "created_at": m.created_at.isoformat() if m.created_at else None}
            for m in mems
        ],
        "latency_ms": latency_ms,
        "stored_count": len(stored),
        "compressed": compressed,
        "thread_id": thread_id,
    }


@app.route("/api/auth/register", methods=["POST"])
def register():
    data = request.get_json() or {}
    username, password, err = _validate_auth_payload(data)
    if err:
        return jsonify({"error": err}), 400
    user_id, create_err = _create_user(username, password)
    if create_err:
        return jsonify({"error": create_err}), 409
    default_thread = _create_thread(user_id, title="New chat", is_temporary=False)
    _backfill_legacy_rows(user_id, default_thread["id"])
    _set_session_user(user_id, username)
    return jsonify({
        "user": {"id": user_id, "username": username},
        "default_thread_id": default_thread["id"],
    })


@app.route("/api/auth/login", methods=["POST"])
def login():
    data = request.get_json() or {}
    username = (data.get("username") or "").strip()
    password = (data.get("password") or "").strip()
    if not username or not password:
        return jsonify({"error": "Username and password are required."}), 400
    row = _find_user_by_username(username)
    if not row or not check_password_hash(row["password_hash"], password):
        return jsonify({"error": "Invalid username or password."}), 401
    default_thread_id = _ensure_default_thread(row["id"])
    _set_session_user(row["id"], row["username"])
    return jsonify({
        "user": {"id": row["id"], "username": row["username"]},
        "default_thread_id": default_thread_id,
    })


@app.route("/api/auth/logout", methods=["POST"])
def logout():
    uid = session.get("user_id")
    if uid is not None:
        for key in list(_user_buffers.keys()):
            if key[0] == uid:
                _user_buffers.pop(key, None)
    session.clear()
    return jsonify({"ok": True})


@app.route("/api/auth/me", methods=["GET"])
def auth_me():
    user = _current_user()
    if not user:
        return jsonify({"authenticated": False, "user": None})
    default_thread_id = _ensure_default_thread(user["id"])
    return jsonify({
        "authenticated": True,
        "user": user,
        "default_thread_id": default_thread_id,
    })


@app.route("/api/chat", methods=["POST"])
@_login_required
def chat(user):
    data = request.get_json() or {}
    message = (data.get("message") or "").strip()
    if not message:
        return jsonify({"error": "Message is required"}), 400
    thread, thread_err = _resolve_thread(user["id"], data.get("thread_id"))
    if thread_err:
        payload, code = thread_err
        return jsonify(payload), code
    try:
        result = _process_message(
            user_id=user["id"],
            thread_id=thread["id"],
            user_message=message,
            store_data=not thread["is_temporary"],
        )
        result["thread"] = _get_thread(user["id"], thread["id"])
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/messages", methods=["GET"])
@_login_required
def get_messages(user):
    thread, thread_err = _resolve_thread(user["id"], request.args.get("thread_id"))
    if thread_err:
        payload, code = thread_err
        return jsonify(payload), code
    if thread["is_temporary"]:
        buffer = _get_user_buffer(user["id"], thread["id"], is_temporary=True)
        messages = [
            {
                "role": m.role,
                "content": m.content,
                "created_at": m.timestamp.isoformat(),
            }
            for m in buffer.messages
        ]
    else:
        messages = _get_messages(user["id"], thread["id"])
    return jsonify({"thread": thread, "messages": messages})


@app.route("/api/threads", methods=["GET"])
@_login_required
def get_threads(user):
    _ensure_default_thread(user["id"])
    return jsonify({"threads": _list_threads(user["id"])})


@app.route("/api/threads", methods=["POST"])
@_login_required
def create_thread(user):
    data = request.get_json() or {}
    is_temporary = bool(data.get("temporary"))
    default_title = "Temporary chat" if is_temporary else "New chat"
    title = _sanitize_thread_title(data.get("title") or default_title)
    thread = _create_thread(user["id"], title=title, is_temporary=is_temporary)
    return jsonify({"thread": thread}), 201


@app.route("/api/threads/<int:thread_id>", methods=["DELETE"])
@_login_required
def delete_thread(user, thread_id: int):
    next_thread_id = _delete_thread(user["id"], thread_id)
    if next_thread_id is None:
        return jsonify({"error": "Thread not found."}), 404
    return jsonify({
        "ok": True,
        "next_thread_id": next_thread_id,
        "threads": _list_threads(user["id"]),
    })


@app.route("/api/memories", methods=["GET"])
@_login_required
def get_memories(user):
    """Return stored memories for inspector. Optional query for retrieval."""
    query = request.args.get("query", "").strip()
    category = request.args.get("category")
    thread_id = None
    raw_thread_id = request.args.get("thread_id")
    if raw_thread_id not in (None, ""):
        thread, thread_err = _resolve_thread(user["id"], raw_thread_id)
        if thread_err:
            payload, code = thread_err
            return jsonify(payload), code
        thread_id = thread["id"]
    if query:
        mems = retrieve(
            query,
            top_k=20,
            category=category or None,
            user_id=user["id"],
            thread_id=thread_id,
        )
    else:
        mems = get_all_memories(user_id=user["id"], thread_id=thread_id)
        if category and category in CATEGORIES:
            mems = [m for m in mems if m.category == category]
    return jsonify({
        "memories": [
            {
                "id": m.id,
                "content": m.content,
                "category": m.category,
                "created_at": m.created_at.isoformat() if m.created_at else None,
            }
            for m in mems
        ],
    })


@app.route("/api/health", methods=["GET"])
@_login_required
def health(user):
    thread_id = None
    raw_thread_id = request.args.get("thread_id")
    if raw_thread_id not in (None, ""):
        thread, thread_err = _resolve_thread(user["id"], raw_thread_id)
        if thread_err:
            payload, code = thread_err
            return jsonify(payload), code
        thread_id = thread["id"]
    return jsonify({
        "openrouter_available": is_available(),
        "ai_available": is_available(),
        "memory_count": get_memory_count(user_id=user["id"], thread_id=thread_id),
        "fallback_count": _fallback_count,
        "last_api_success": _last_api_success,
        "thread_id": thread_id,
    })


@app.route("/")
def index():
    return send_from_directory(DASHBOARD_DIR, "index.html")


@app.route("/<path:path>")
def serve_static(path):
    return send_from_directory(DASHBOARD_DIR, path)


# Ensure schema exists for both direct run and flask --app usage.
init_db()


if __name__ == "__main__":
    host = os.environ.get("HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", "5000"))
    debug = os.environ.get("FLASK_DEBUG", "1").strip().lower() in ("1", "true", "yes")
    app.run(host=host, port=port, debug=debug)
