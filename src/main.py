"""
Main entry point - conversational AI with hierarchical memory.

Run from project root: python -m src.main
"""

import re
import sys
from datetime import datetime, timedelta
from pathlib import Path

# Load .env early so API keys are available
sys.path.insert(0, str(Path(__file__).parent))
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
except ImportError:
    pass

from memory.short_term import ShortTermBuffer
from memory.long_term import init_db, add_memory, get_memory_count, get_all_memories, delete_memories
from memory.extractor import extract_local, extract_with_openrouter
from memory.embeddings import encode, get_backend
from memory.retrieval import retrieve
from memory.compression import maybe_compress
from llm.openrouter import generate, is_available, is_quota_saving
from config import (
    MAX_SHORT_TERM_MESSAGES,
    TOP_K_MEMORIES,
    CATEGORIES,
)

def _get_fallback_message() -> str:
    """Return helpful message when AI provider is unavailable."""
    import os
    from pathlib import Path
    key = os.environ.get("OPENROUTER_API_KEY")
    env_path = Path(__file__).resolve().parent.parent / ".env"
    if not key:
        return (
            "I can't connect to the AI right now. To enable AI responses:\n"
            f"  1. Create {env_path} with: OPENROUTER_API_KEY=your_key\n"
            "  2. Get a key at https://openrouter.ai/keys\n"
            "  3. Restart the app."
        )
    return "The AI service is temporarily unavailable. I've noted your message—please try again in a moment."


CLI_HELP = """
Commands:
  /memories [category]  List stored memories (optional: personal, food, travel, misc)
  /stats                Show memory statistics
  /export [file]        Export memories to JSON (default: data/memories_export.json)
  /clear                Delete all memories (confirmation required)
  /help                 Show this help
  quit, exit, q         Exit chat
"""

SYSTEM_INSTRUCTION = """You are a helpful conversational assistant with long-term memory of the user.
Use the provided "Relevant memories" to personalize your responses. Be concise and natural.
If memories conflict with what the user just said, prioritize the most recent conversation."""

_DATETIME_QUERY_RE = re.compile(
    r"(what\s+time\s+is\s+it|what'?s\s+the\s+time|current\s+time|time\s+now|time\s+right\s+now|"
    r"today'?s\s+date|date\s+today|current\s+date|"
    r"what\s+day\s+is\s+it|which\s+day\s+is\s+it|"
    r"date\s+and\s+time|current\s+date\s+and\s+time|"
    r"tomorrow\s+date|tommorow\s+date|yesterday\s+date)",
    re.IGNORECASE,
)


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
        or ("what day is it" in t)
        or ("which day is it" in t)
        or bool(re.search(r"\b(what|which)\s+(day|date|month|year)\b", t))
        or bool(re.search(r"\b(current|today'?s)\s+(date|day|month|year)\b", t))
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


def build_context(short_term: ShortTermBuffer, memories_text: str) -> str:
    """Build the context string for the LLM."""
    parts = []
    if memories_text:
        parts.append("Relevant memories about the user:\n" + memories_text)
    parts.append("\nRecent conversation:\n" + short_term.format_for_context())
    return "\n".join(parts)


def get_response(user_message: str, short_term: ShortTermBuffer) -> str:
    """Generate response using configured AI provider or fallback."""
    if _is_datetime_request(user_message):
        return _current_datetime_reply(user_message)
    mems = retrieve(user_message, top_k=TOP_K_MEMORIES)
    memories_text = "\n".join(f"- [{m.category}] {m.content}" for m in mems) if mems else ""
    context = build_context(short_term, memories_text)
    prompt = f"{context}\n\nAssistant:"
    response = generate(prompt, system_instruction=SYSTEM_INSTRUCTION)
    if response:
        return response
    return _get_fallback_message()


def process_and_store_facts(user_message: str, use_ai: bool = True) -> list[dict]:
    """Extract facts and store them with embeddings. Skip near-duplicates."""
    from config import DUPLICATE_SIMILARITY_THRESHOLD
    from memory.long_term import has_similar_memory

    extracted = extract_with_openrouter(user_message) if use_ai else extract_local(user_message)
    stored = []
    for item in extracted:
        content = item["content"]
        category = item["category"]
        try:
            embedding = encode(content)
        except Exception:
            embedding = None  # store anyway so we don't lose the fact
        if embedding and has_similar_memory(embedding, category, DUPLICATE_SIMILARITY_THRESHOLD):
            continue
        add_memory(content=content, category=category, embedding=embedding)
        stored.append(item)
    return stored


def handle_cli_command(cmd: str) -> bool:
    """Handle /commands. Returns True if handled (no further processing)."""
    cmd = cmd.strip().lower()
    if cmd == "/help":
        print(CLI_HELP)
        return True
    if cmd == "/stats":
        count = get_memory_count()
        mems = get_all_memories()
        by_cat = {}
        for m in mems:
            by_cat[m.category] = by_cat.get(m.category, 0) + 1
        print(f"\nMemories: {count} total")
        for c in CATEGORIES:
            print(f"  {c}: {by_cat.get(c, 0)}")
        print()
        return True
    if cmd.startswith("/memories"):
        parts = cmd.split(maxsplit=1)
        cat = parts[1] if len(parts) > 1 else None
        mems = get_all_memories()
        if cat and cat in CATEGORIES:
            mems = [m for m in mems if m.category == cat]
        if not mems:
            print("\nNo memories stored.\n")
        else:
            print(f"\n{len(mems)} memories:\n")
            for m in mems:
                print(f"  [{m.category}] {m.content}")
            print()
        return True
    if cmd == "/clear":
        confirm = input("Delete all memories? (yes/no): ").strip().lower()
        if confirm == "yes":
            mems = get_all_memories()
            delete_memories([m.id for m in mems if m.id])
            print("All memories cleared.\n")
        else:
            print("Cancelled.\n")
        return True
    if cmd.startswith("/export"):
        import json
        from pathlib import Path
        parts = cmd.split(maxsplit=1)
        out_path = Path(parts[1]) if len(parts) > 1 else Path("data/memories_export.json")
        out_path.parent.mkdir(parents=True, exist_ok=True)
        mems = get_all_memories()
        data = [{"content": m.content, "category": m.category, "created_at": m.created_at.isoformat() if m.created_at else None} for m in mems]
        with open(out_path, "w") as f:
            json.dump(data, f, indent=2)
        print(f"Exported {len(mems)} memories to {out_path}\n")
        return True
    return False


def main():
    init_db()
    buffer = ShortTermBuffer(max_size=MAX_SHORT_TERM_MESSAGES)
    has_ai = is_available()

    print("=== Memory-Enabled Conversational AI ===")
    print("Type /help for commands, 'quit' to exit.\n")
    print(f"(Embeddings: {get_backend()})")
    if has_ai:
        if is_quota_saving():
            print("(AI provider connected - quota-saver mode is enabled)")
        else:
            print("(AI provider connected - using AI responses and smart extraction)")
    else:
        print("(AI key not found - using local fallback. Set OPENROUTER_API_KEY in .env for full features)")

    while True:
        user_input = input("You: ").strip()
        if not user_input:
            continue
        if user_input.lower() in ("quit", "exit", "q"):
            print("Goodbye!")
            break
        if user_input.startswith("/"):
            if handle_cli_command(user_input):
                continue

        buffer.add("user", user_input)

        # Deterministic answer for current date/time queries (skip extraction/compression/model).
        if _is_datetime_request(user_input):
            response = _current_datetime_reply(user_input)
            buffer.add("assistant", response)
            print(f"\nAssistant: {response}\n")
            continue

        # Extract and store facts (use local extraction when saving quota — free tier is 20/day)
        stored = process_and_store_facts(user_input, use_ai=has_ai and not is_quota_saving())
        if stored:
            for s in stored:
                print(f"  [Stored] [{s['category']}] {s['content']}")

        # Compress if needed (skip when saving quota to avoid extra AI calls)
        if not is_quota_saving() and maybe_compress():
            print("  [Compressed older memories]")

        # Generate response
        response = get_response(user_input, buffer)
        buffer.add("assistant", response)

        print(f"\nAssistant: {response}\n")


if __name__ == "__main__":
    main()
