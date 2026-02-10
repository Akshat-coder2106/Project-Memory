"""
Backend API for the memory dashboard. Links frontend to the memory system.
"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
except ImportError:
    pass

from flask import Flask, request, jsonify, send_from_directory

from memory.short_term import ShortTermBuffer
from memory.long_term import init_db, add_memory, get_all_memories, get_memory_count
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

# Path to dashboard (served as static files)
DASHBOARD_DIR = Path(__file__).resolve().parent.parent / "dashboard"

SYSTEM_INSTRUCTION = """You are a helpful conversational assistant with long-term memory of the user.
Use the provided "Relevant memories" to personalize your responses. Be concise and natural.
If memories conflict with what the user just said, prioritize the most recent conversation."""

# Session state: one buffer per app (single-user for now)
buffer = ShortTermBuffer(max_size=MAX_SHORT_TERM_MESSAGES)
_last_api_success = None
_fallback_count = 0


def _get_fallback_message():
    import os
    return (
        "I can't connect to the AI right now. Set OPENROUTER_API_KEY in .env and restart."
        if not os.environ.get("OPENROUTER_API_KEY")
        else "The AI service is temporarily unavailable. Please try again in a moment."
    )


def _process_message(user_message: str):
    global _last_api_success, _fallback_count
    from memory.long_term import has_similar_memory

    start = time.perf_counter()
    buffer.add("user", user_message)

    # Extract and store
    has_openrouter = is_available()
    extracted = extract_with_openrouter(user_message) if has_openrouter else extract_local(user_message)
    stored = []
    for item in extracted:
        content = item["content"]
        category = item["category"]
        embedding = encode(content)
        if has_similar_memory(embedding, category, DUPLICATE_SIMILARITY_THRESHOLD):
            continue
        add_memory(content=content, category=category, embedding=embedding)
        stored.append(item)

    # Compress
    compressed = maybe_compress()

    # Retrieve and generate
    mems = retrieve(user_message, top_k=TOP_K_MEMORIES)
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
    }


@app.route("/api/chat", methods=["POST"])
def chat():
    data = request.get_json() or {}
    message = (data.get("message") or "").strip()
    if not message:
        return jsonify({"error": "Message is required"}), 400
    try:
        result = _process_message(message)
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/messages", methods=["GET"])
def get_messages():
    """Return conversation history (user + assistant only, no stored-words metadata)."""
    msgs = [
        {"role": m.role, "content": m.content}
        for m in buffer.messages
    ]
    return jsonify({"messages": msgs})


@app.route("/api/memories", methods=["GET"])
def get_memories():
    """Return stored memories for inspector. Optional query for retrieval."""
    query = request.args.get("query", "").strip()
    category = request.args.get("category")
    if query:
        mems = retrieve(query, top_k=20, category=category or None)
    else:
        mems = get_all_memories()
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
def health():
    return jsonify({
        "gemini_available": is_available(),
        "memory_count": get_memory_count(),
        "fallback_count": _fallback_count,
        "last_api_success": _last_api_success,
    })


@app.route("/")
def index():
    return send_from_directory(DASHBOARD_DIR, "index.html")


@app.route("/<path:path>")
def serve_static(path):
    return send_from_directory(DASHBOARD_DIR, path)


if __name__ == "__main__":
    init_db()
    app.run(host="127.0.0.1", port=5000, debug=True)
